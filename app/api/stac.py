import enum
import logging
import math
import mimetypes
import os
import re
from datetime import datetime as dt
from pathlib import Path
from types import EllipsisType
from typing import Annotated, NotRequired, TypedDict, Unpack
from urllib import parse

from fastapi import Depends, HTTPException, Request
from pydantic import (
    BaseModel,
    Field,
    Json,
    SerializationInfo,
    computed_field,
    field_serializer,
    field_validator,
)

from app.api.gitlab import (
    GITLAB_LICENSES_SPDX_MAPPING,
    GitlabClient,
    GitlabProject,
    GitlabProjectFile,
    GitlabProjectRelease,
    project_issues_url,
    project_url,
)
from app.config import GITLAB_URL, STAC_CATEGORIES
from app.dependencies import GitlabToken
from app.utils import markdown as md
from app.utils.geo import find_parent_of_hashes, hash_polygon
from app.utils.http import is_local, url_for

logger = logging.getLogger("app")

MEDIA_TYPES = {
    "text": "text/plain",
    "json": "application/json",
    "xml": "application/xml",
    "yaml": "text/x-yaml",
    "zip": "application/zip",
    "geotiff": "image/tiff; application=geotiff",
    "cog": "image/tiff; application=geotiff; profile=cloud-optimized",
    "geojson": "application/geo+json",
    "compose": "text/x-yaml; application=compose",
    "notebook": "application/x-ipynb+json",
}

ML_ASSETS_DEFAULT_GLOBS = {
    "inference-runtime": "inferencing.yml",
    "training-runtime": "training.yml",
    "checkpoint": "*.pt",
}

FILE_ASSET_PREFIX = "file://"


class STACSearchQuery(BaseModel):
    limit: Annotated[int, Field(strict=True, gt=0)] = 10
    bbox: list[float] = Field(default_factory=list)
    datetime: str | None = Field(default=None)
    intersects: Json = Field(default=None)
    ids: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    q: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)

    @field_validator("datetime")
    @classmethod
    def validate_datetime(cls, d: str) -> str:
        if d:
            d1, *do = d.split("/")
            dt.fromisoformat(d1)
            if do:
                d2 = do[0]
                dt.fromisoformat(d2)
        return d

    @computed_field
    def datetime_range(self) -> tuple[dt, dt] | None:
        if self.datetime:
            start_dt_str, *other_dts_str = self.datetime.split("/")
            start_dt = dt.fromisoformat(start_dt_str)
            if other_dts_str:
                end_dt_str = other_dts_str[0]
                end_dt = dt.fromisoformat(end_dt_str)
            else:
                end_dt = start_dt
            return start_dt, end_dt
        return None

    @field_serializer("bbox", "ids", "collections", "q", when_used="unless-none")
    def serialize_lists(self, v: list[str | float], _info: SerializationInfo) -> str:
        return ",".join(str(e) for e in v)


class STACContext(TypedDict):
    request: Request
    token: GitlabToken


class Pagination(TypedDict):
    limit: int
    matched: int
    returned: int
    page: int


class Category(TypedDict):
    id: str
    title: str
    description: NotRequired[str]
    preview: NotRequired[str]
    features: TypedDict
    gitlab_topic: NotRequired[str]


CategoryName = enum.StrEnum("CategoryName", {k: k for k in STAC_CATEGORIES})


def get_category(category_id: str) -> Category | None:
    if category_id in STAC_CATEGORIES:
        return Category(id=category_id, **STAC_CATEGORIES[category_id])
    return None


def get_categories() -> list[Category]:
    return [get_category(category_id) for category_id in STAC_CATEGORIES]


def get_category_from_collection_id(collection_id: CategoryName) -> Category:
    category = get_category(category_id=collection_id)
    if not category:
        logger.error(
            f"Collection '{collection_id}' requested but its configuration is missing."
        )
        raise HTTPException(status_code=404, detail="Collection not found")

    return category


CategoryFromCollectionIdDep = Annotated[
    Category, Depends(get_category_from_collection_id)
]


async def search_projects(
    search_query: STACSearchQuery, client: GitlabClient
) -> list[GitlabProject]:
    projects: dict[int, GitlabProject] = {}

    topics: list[str] = []
    for collection_id in set(search_query.collections):
        category = get_category(collection_id)
        if category:
            topics.append(category["gitlab_topic"])
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Collections should be one of: {', '.join(STAC_CATEGORIES)}",
            )
    _allowed_categories_topics = (
        topics if topics else [c["gitlab_topic"] for c in get_categories()]
    )
    topics.extend(search_query.topics)

    # Collections search
    projects |= {p["id"]: p for p in await client.get_projects(*topics)}

    # Spatial extent search
    extent_search: dict[int, GitlabProject] = {}
    if search_query.bbox:
        bbox_geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [search_query.bbox[0], search_query.bbox[1]],
                    [search_query.bbox[2], search_query.bbox[1]],
                    [search_query.bbox[2], search_query.bbox[3]],
                    [search_query.bbox[0], search_query.bbox[3]],
                    [search_query.bbox[0], search_query.bbox[1]],
                ]
            ],
        }
        cells = hash_polygon(bbox_geojson)
        extent_search = [" ".join(cells)]
        try:
            while True:
                cells = find_parent_of_hashes(cells)
                extent_search.append(" ".join(cells))
        except:  # nosec B110
            pass
        for query in extent_search:
            gitlab_search = await client.search(scope="projects", query=query)
            gitlab_search = [
                project
                for project in gitlab_search
                if any(t in project["topics"] for t in _allowed_categories_topics)
            ]
            extent_search |= {p["id"]: p for p in gitlab_search}

    # Free-text search
    q_search: dict[int, GitlabProject] = {}
    if search_query.q:
        for query in search_query.q:
            gitlab_search = await client.search(scope="projects", query=query)
            gitlab_search = [
                project
                for project in gitlab_search
                if any(t in project["topics"] for t in _allowed_categories_topics)
            ]
            q_search |= {p["id"]: p for p in gitlab_search}

    projects = _search_aggregate(projects, extent_search, q_search)

    # Ids search
    if search_query.ids and not projects:
        for stac_id in search_query.ids:
            stac_id_parse = _parse_project_stac_id(stac_id)
            if stac_id_parse:
                category, project_id = stac_id_parse
                try:
                    project = await client.get_project(project_id)
                    if category["gitlab_topic"] in project["topics"]:
                        projects[project["id"]] = project
                except HTTPException as http_exc:
                    if http_exc.status_code != 404:
                        logger.exception(http_exc)
    elif search_query.ids:
        projects = {
            p["id"]: p
            for p in projects.values()
            if _get_project_stac_id(project=p, category=get_project_category(p))
            in search_query.ids
        }

    # Temporal extent search
    if dt_range := search_query.datetime_range:
        search_start_dt, search_end_dt = dt_range

        def temporal_filter(project_item: tuple[int, GitlabProject]) -> bool:
            _, project = project_item
            _, temporal_extent = _get_extent(project, {})
            p_start_dt = dt.fromisoformat(temporal_extent[0])
            p_end_dt = dt.fromisoformat(temporal_extent[0])
            return search_start_dt <= p_start_dt <= p_end_dt <= search_end_dt

        projects = dict(filter(temporal_filter, projects.items()))

    return list(projects.values())


def _search_aggregate(
    projects: dict[int, GitlabProject], *search_results: dict[int, GitlabProject]
) -> None:
    _projects = dict(projects)
    for search_result in search_results:
        if _projects and search_result:
            _projects = {
                p_id: p for p_id, p in _projects.items() if p_id in search_result
            }
        else:
            _projects |= search_result
    return _projects


def paginate_projects(
    projects: list[GitlabProject], page: int, per_page: int
) -> tuple[list[GitlabProject], Pagination]:
    page_projects = projects[(page - 1) * per_page : page * per_page]
    pagination = Pagination(
        limit=per_page, matched=len(projects), returned=len(page_projects), page=page
    )
    return page_projects, pagination


def get_project_category(project: GitlabProject) -> Category | None:
    categories = get_categories()
    for category in categories:
        if category["gitlab_topic"] in project["topics"]:
            return category
    return None


def build_stac_root(
    root_config: dict,
    conformance_classes: list[str],
    categories: list[str],
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    title = root_config.get("title", "GitLab STAC")
    description = root_config.get(
        "description",
        f"Catalog generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHUB.",
    )
    logo = root_config.get("logo")

    links = [
        {
            "rel": "child",
            "type": "application/geo+json",
            "href": url_for(
                _request,
                "stac2_collection",
                path=dict(collection_id=category_id),
                query={**_token.query},
            ),
        }
        for category_id in categories
    ]

    if logo:
        logo_media_type, _ = mimetypes.guess_type(logo)
        links.append(
            {
                "rel": "preview",
                "type": logo_media_type,
                "href": logo,
            }
        )

    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": root_config["id"],
        "title": title,
        "description": description,
        "links": [
            {
                "rel": "self",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.1",
                "href": url_for(_request, "index") + "openapi.json",
                "title": "OpenAPI definition",
            },
            {
                "rel": "service-doc",
                "type": "text/html",
                "href": url_for(_request, "index") + "api/docs",
                "title": "OpenAPI interactive docs: Swagger UI",
            },
            {
                "rel": "conformance",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_conformance",
                    query={**_token.query},
                ),
            },
            {
                "rel": "data",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_collections",
                    query={**_token.query},
                ),
            },
            {
                "rel": "search",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    "stac2_search",
                    query={**_token.query},
                ),
                "method": "GET",
            },
            *links,
        ],
        "conformsTo": conformance_classes,
    }


def build_stac_collections(
    categories: list[Category], **context: Unpack[STACContext]
) -> dict:
    _request = context["request"]
    _token = context["token"]

    collections = [
        build_stac_collection(
            category=category,
            request=_request,
            token=_token,
        )
        for category in categories
    ]
    _collections_len = len(collections)
    return {
        "collections": collections,
        "links": [
            {
                "rel": "self",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_collections",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
        ],
        "context": {
            "page": 1,
            "limit": _collections_len,
            "matched": _collections_len,
            "returned": _collections_len,
        },
    }


def build_stac_collection(category: Category, **context: Unpack[STACContext]) -> dict:
    _request = context["request"]
    _token = context["token"]

    title = category["title"]
    description = category.get(
        "description",
        f"STAC {title} generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHUB.",
    )
    logo = category.get("logo")

    links = []

    if logo:
        logo_media_type, _ = mimetypes.guess_type(logo)
        links.append(
            {
                "rel": "preview",
                "type": logo_media_type,
                "href": logo,
            }
        )

    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Collection",
        "id": category["id"],
        "title": title,
        "description": description,
        "license": "proprietary",
        "keywords": [category["id"]],
        "providers": [
            {
                "name": f"GitLab ({GITLAB_URL})",
                "roles": ["host"],
                "url": GITLAB_URL,
            },
        ],
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [[None, None]]},
        },
        "links": [
            {
                "rel": "self",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_collection",
                    path=dict(collection_id=category["id"]),
                    query={**_token.query},
                ),
            },
            {
                "rel": "parent",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "items",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    "stac2_collection_items",
                    path=dict(collection_id=category["id"]),
                    query={**_token.query},
                ),
            },
            *links,
        ],
    }


def build_features_collection(
    features: list[dict],
    pagination: Pagination,
    route: str,
    category: Category | None,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    links = []

    if category:
        links.append(
            {
                "rel": "collection",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_collection",
                    path=dict(collection_id=category["id"]),
                    query={**_token.query},
                ),
            }
        )

    query_params = dict(_request.query_params)

    if pagination["page"] > 1:
        prev_params = query_params.copy()
        prev_params["page"] = pagination["page"] - 1
        links.append(
            {
                "rel": "prev",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query={**prev_params, **_token.query},
                ),
                "type": "application/geo+json",
            }
        )

        first_params = query_params.copy()
        first_params["page"] = 1
        links.append(
            {
                "rel": "first",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query={**first_params, **_token.query},
                ),
                "type": "application/geo+json",
            }
        )

    if pagination["page"] * pagination["limit"] < pagination["matched"]:
        next_params = query_params.copy()
        next_params["page"] = pagination["page"] + 1

        links.append(
            {
                "rel": "next",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query={**next_params, **_token.query},
                ),
                "type": "application/geo+json",
            }
        )

        last_params = query_params.copy()
        last_params["page"] = math.ceil(pagination["matched"] / pagination["limit"])
        links.append(
            {
                "rel": "last",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query={**last_params, **_token.query},
                ),
                "type": "application/geo+json",
            }
        )

    return {
        "type": "FeatureCollection",
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "context": {
            "limit": pagination["limit"],
            "matched": pagination["matched"],
            "returned": pagination["returned"],
        },
        "numberMatched": pagination["matched"],
        "numberReturned": pagination["returned"],
        "features": features,
        "links": [
            {
                "rel": "self",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query={**_request.query_params, **_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac2_root",
                    query={**_token.query},
                ),
            },
            *links,
        ],
    }


def build_stac_item_preview(
    project: GitlabProject,
    readme: str,
    category: Category | None,
    **context: Unpack[STACContext],
) -> dict:
    if not category:
        raise HTTPException(
            status_code=500, detail="Unexpected error, project have no category"
        )

    readme_doc, readme_metadata = md.parse(readme)

    # STAC data
    description = _get_preview_description(project, readme_doc)
    keywords = _get_tags(project, category)
    preview, preview_media_type = _get_preview(readme_metadata, readme_doc)
    spatial_extent, _ = _get_extent(project, readme_metadata)

    # STAC generation
    default_links, default_assets = get_stac_item_default_links_and_assets(
        project, category, preview, preview_media_type, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": _get_project_stac_id(project, category),
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    (spatial_extent[0], spatial_extent[1]),
                    (spatial_extent[2], spatial_extent[1]),
                    (spatial_extent[2], spatial_extent[3]),
                    (spatial_extent[0], spatial_extent[3]),
                    (spatial_extent[0], spatial_extent[1]),
                ]
            ],
        },
        "bbox": spatial_extent,
        "properties": {
            "title": project["name"],
            "description": description,
            "datetime": project["last_activity_at"],
            "keywords": keywords,
            "sharinghub:stars": project["star_count"],
        },
        "links": default_links,
        "assets": default_assets,
    }


def build_stac_item(
    project: GitlabProject,
    readme: str,
    files: list[GitlabProjectFile],
    assets_rules: list[str],
    release: GitlabProjectRelease | None,
    release_source_format: str,
    category: Category,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    readme_doc, readme_metadata = md.parse(readme)
    assets_mapping = _get_assets_mapping(assets_rules, readme_metadata)

    # STAC data

    description = _get_description(project, readme_doc, **context)
    keywords = _get_tags(project, category)
    preview, preview_media_type = _get_preview(readme_metadata, readme_doc)
    license, license_url = _get_license(project, readme_metadata)
    producer, producer_url = _get_producer(project, readme_metadata)
    spatial_extent, temporal_extent = _get_extent(project, readme_metadata)
    files_assets = _get_files_assets(files, assets_mapping)
    resources_links = _get_resources_links(readme_metadata, **context)

    # _ Extensions

    # __ sharing hub extensions
    sharinghub_properties = _get_sharinghub_properties(category, readme_metadata)

    # __ Scientific Citation extension (https://github.com/stac-extensions/scientific)
    doi, doi_publications = _get_scientific_citations(readme_metadata, readme_doc)
    doi_link, doi_citation = doi

    # __ ML Model Extension Specification (https://github.com/stac-extensions/ml-model)
    ml_properties, ml_assets, ml_links = _get_machine_learning(
        readme_metadata, resources_links
    )

    # STAC generation

    stac_extensions = [
        "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
    ]

    fields = {}
    assets = {}
    links = []

    if license_url:
        links.append(
            {
                "rel": "license",
                "href": license_url,
            }
        )
    if license:
        fields["license"] = license

    for file_path, file_media_type in files_assets.items():
        asset_id = _get_file_asset_id(file_path)
        assets[asset_id] = {
            "href": url_for(
                _request,
                "download_gitlab_file",
                path=dict(
                    project_id=project["id"],
                    ref=project["default_branch"],
                    file_path=file_path,
                ),
                query={**_token.rc_query},
            ),
            "title": file_path,
            "roles": ["data"],
        }
        if file_media_type:
            assets[asset_id]["type"] = file_media_type

    if release:
        archive_url = url_for(
            _request,
            "download_gitlab_archive",
            path=dict(
                project_id=project["id"],
                ref=release["tag_name"],
                format=release_source_format,
            ),
            query={**_token.rc_query},
        )
        media_type, _ = mimetypes.guess_type(f"archive.{release_source_format}")
        assets["release"] = {
            "href": archive_url,
            "title": f"Release {release['tag_name']}: {release['name']}",
            "roles": ["source"],
        }
        if release["description"]:
            assets["release"]["description"] = release["description"]
        if media_type:
            assets["release"]["type"] = media_type

    if doi_link:
        fields["sci:doi"] = parse.urlparse(doi_link).path.removeprefix("/")
        links.append(
            {
                "rel": "cite-as",
                "href": doi_link,
            }
        )
    if doi_citation:
        fields["sci:citation"] = doi_citation
    if doi_publications:
        fields["sci:publications"] = [
            {
                "doi": parse.urlparse(_pub_doi_link).path.removeprefix("/"),
                "citation": _pub_citation,
            }
            for _pub_doi_link, _pub_citation in doi_publications
        ]

    if ml_properties:
        stac_extensions.append(
            "https://stac-extensions.github.io/ml-model/v1.0.0/schema.json"
        )

        for prop, val in ml_properties.items():
            fields[f"ml-model:{prop}"] = val

        for ml_asset_role, patterns in ml_assets.items():
            _patterns = (
                patterns
                if patterns is not Ellipsis
                else [ML_ASSETS_DEFAULT_GLOBS.get(ml_asset_role)]
            )
            if _patterns:
                for _pattern in _patterns:
                    for asset_id in assets:
                        fpath = Path(asset_id.removeprefix(FILE_ASSET_PREFIX))
                        if asset_id.startswith(FILE_ASSET_PREFIX) and fpath.match(
                            _pattern
                        ):
                            assets[asset_id]["roles"].append(
                                f"ml-model:{ml_asset_role}"
                            )

        for relation_type, (media_type, values) in ml_links.items():
            hrefs = [href for _, href in values]
            for link in links:
                if link["href"] in hrefs:
                    links.remove(link)
            for link_title, link_href in values:
                _link = {
                    "rel": f"ml-model:{relation_type}",
                    "href": link_href,
                    "title": link_title,
                }
                if media_type:
                    _link["type"] = media_type
                links.append(_link)

    if sharinghub_properties:
        for prop, val in sharinghub_properties.items():
            fields[f"sharinghub:{prop}"] = val

    default_links, default_assets = get_stac_item_default_links_and_assets(
        project, category, preview, preview_media_type, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": stac_extensions,
        "type": "Feature",
        "id": _get_project_stac_id(project, category),
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    (spatial_extent[0], spatial_extent[1]),
                    (spatial_extent[2], spatial_extent[1]),
                    (spatial_extent[2], spatial_extent[3]),
                    (spatial_extent[0], spatial_extent[3]),
                    (spatial_extent[0], spatial_extent[1]),
                ]
            ],
        },
        "bbox": spatial_extent,
        "properties": {
            "title": project["name"],
            "description": description,
            "datetime": project["last_activity_at"],
            "start_datetime": temporal_extent[0],
            "end_datetime": temporal_extent[1],
            "created": temporal_extent[0],
            "updated": temporal_extent[1],
            "keywords": keywords,
            "providers": [
                {
                    "name": f"GitLab ({GITLAB_URL})",
                    "roles": ["host"],
                    "url": project_url(GITLAB_URL, project),
                },
                {
                    "name": producer,
                    "roles": ["producer"],
                    "url": producer_url,
                },
            ],
            **fields,
            "sharinghub:name": project["name_with_namespace"],
            "sharinghub:path": project["path_with_namespace"],
            "sharinghub:id": project["id"],
            "sharinghub:stars": project["star_count"],
        },
        "links": [
            *default_links,
            {
                "rel": "bug_tracker",
                "type": "text/html",
                "href": project_issues_url(GITLAB_URL, project),
                "title": "Issues",
            },
            *(
                {
                    "rel": "derived_from" if "stac" in _labels else "extras",
                    "type": "application/json",
                    "href": _href,
                    "title": _title,
                }
                for _title, _href, _labels in resources_links
            ),
            *links,
        ],
        "assets": default_assets | assets,
    }


def get_stac_item_default_links_and_assets(
    project: GitlabProject,
    category: Category,
    preview: str | None,
    preview_media_type: str | None,
    **context: Unpack[STACContext],
) -> tuple[list[dict], dict[str, dict]]:
    _request = context["request"]
    _token = context["token"]

    assets = {}
    links = []
    if is_local(preview):
        preview = url_for(
            _request,
            "download_gitlab_file",
            path=dict(
                project_id=project["id"],
                ref=project["default_branch"],
                file_path=preview,
            ),
            query={**_token.rc_query},
        )
    if preview:
        assets["preview"] = {
            "href": preview,
            "title": "Preview",
            "roles": ["thumbnail"],
        }
        if preview_media_type:
            assets["preview"]["type"] = preview_media_type
        links.append(
            {
                "rel": "preview",
                "href": preview,
            }
        )
    return [
        {
            "rel": "self",
            "type": "application/geo+json",
            "href": url_for(
                _request,
                "stac2_collection_feature",
                path=dict(
                    collection_id=category["id"],
                    feature_id=project["path_with_namespace"],
                ),
                query={**_token.query},
            ),
        },
        {
            "rel": "parent",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac2_collection",
                path=dict(collection_id=category["id"]),
                query={**_token.query},
            ),
        },
        {
            "rel": "root",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac2_root",
                query={**_token.query},
            ),
        },
        {
            "rel": "collection",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac2_collection",
                path=dict(collection_id=category["id"]),
                query={**_token.query},
            ),
        },
        *links,
    ], assets


def _get_preview_description(
    project: GitlabProject, md_content: str, wrap_char: int = 150
) -> str:
    description = project["description"]
    if not description:
        description = md_content
        description = md.remove_everything_before_first_heading(description)
        description = md.remove_headings(description)
        description = md.remove_images(description)
        description = md.remove_links(description)
        description = md.clean_new_lines(description)
        description = description[:wrap_char].strip()
        if len(description) == wrap_char:
            description += "..."
    return description if description else None


def _get_description(
    project: GitlabProject, md_content: str, **context: Unpack[STACContext]
) -> str:
    description = md.increase_headings(md_content, 3)
    description = _resolve_images(description, project=project, **context)
    description = md.clean_new_lines(description)
    return description


def _get_tags(project: GitlabProject, category: Category) -> list[str]:
    project_topics = project["topics"]
    project_topics.remove(category["gitlab_topic"])
    return project_topics


def _get_preview(
    metadata: dict,
    md_content: str,
) -> tuple[str | None, str | None]:
    preview = metadata.get("preview")
    preview = metadata.get("thumbnail", preview)
    for link_alt, link_img in md.get_images(md_content):
        if link_alt.lower().strip() in ["preview", "thumbnail"]:
            preview = link_img
    media_type, _ = mimetypes.guess_type(preview) if preview else (None, None)
    return preview, media_type


def _get_extent(
    project: GitlabProject, metadata: dict
) -> tuple[list[float], list[str | None]]:
    extent = metadata.get("extent", {})
    spatial_extent = extent.get("bbox", [-180.0, -90.0, 180.0, 90.0])
    temporal_extent = extent.get(
        "temporal", [project["created_at"], project["last_activity_at"]]
    )
    return spatial_extent, temporal_extent


def _get_assets_mapping(
    assets_rules: list[str], metadata: dict
) -> dict[str, str | None]:
    assets_mapping = {}
    for asset_rule in (*assets_rules, *metadata.get("assets", [])):
        eq_match = asset_rule.split("=")
        glob_match = asset_rule.split("://")
        if len(eq_match) == 2:
            file_ext_glob = f"*.{eq_match[0].lstrip('.')}"
            assets_mapping[file_ext_glob] = MEDIA_TYPES.get(eq_match[1])
        elif len(glob_match) == 2:
            assets_mapping[glob_match[1]] = MEDIA_TYPES.get(glob_match[0])
        else:
            assets_mapping[asset_rule] = None
    return assets_mapping


def _resolve_images(
    md_content: str, project: GitlabProject, **context: Unpack[STACContext]
) -> str:
    _request = context["request"]
    _token = context["token"]

    def _resolve_src(match: re.Match):
        url = match.groupdict()["src"]
        if is_local(url) and not os.path.isabs(url):
            path = os.path.relpath(url)
            url = url_for(
                _request,
                "download_gitlab_file",
                path=dict(
                    project_id=project["id"],
                    ref=project["default_branch"],
                    file_path=path,
                ),
                query={**_token.rc_query},
            )
        return f'src="{url}"'

    def __resolve_md(match: re.Match):
        image = match.groupdict()
        url = image["src"]
        if is_local(url) and not os.path.isabs(url):
            path = os.path.relpath(url)
            url = url_for(
                _request,
                "download_gitlab_file",
                path=dict(
                    project_id=project["id"],
                    ref=project["default_branch"],
                    file_path=path,
                ),
                query={**_token.rc_query},
            )
        return f"![{image['alt']}]({url})"

    md_patched = md_content
    md_patched = re.sub(r"src=(\"|')(?P<src>.*?)(\"|')", _resolve_src, md_patched)
    md_patched = re.sub(md.IMAGE_PATTERN, __resolve_md, md_patched)
    return md_patched


def _get_license(
    project: GitlabProject, metadata: dict
) -> tuple[str | None, str | None]:
    if "license" in metadata:
        # Must be SPDX identifier: https://spdx.org/licenses/
        license = metadata["license"]
        license_url = None
    elif project.get("license"):
        _license = project["license"]["key"]
        _license_html_url = project["license"]["html_url"]
        license = GITLAB_LICENSES_SPDX_MAPPING.get(_license, _license.upper())
        license_url = (
            project["license_url"]
            if project["license_url"]
            else _license_html_url
            if _license_html_url
            else None
        )
    else:
        # Private
        license = None
        license_url = None
    return license, license_url


def _get_producer(project: GitlabProject, metadata: dict) -> tuple[str, str]:
    producer = project["name_with_namespace"].split("/")[0].rstrip()
    producer = metadata.get("producer", producer)
    _producer_path = project["path_with_namespace"].split("/")[0]
    producer_url = f"{GITLAB_URL}/{_producer_path}"
    producer_url = metadata.get("producer_url", producer_url)
    return producer, producer_url


def _get_files_assets(
    files: list[GitlabProjectFile], assets_mapping: dict[str, str | None]
) -> dict[str, str | None]:
    assets = {}
    for file in files:
        fpath = Path(file["path"])
        for glob in assets_mapping:
            if fpath.match(glob):
                if assets_mapping[glob]:
                    media_type = assets_mapping[glob]
                else:
                    media_type, _ = mimetypes.guess_type(fpath)
                if media_type or not assets.get(file["path"]):
                    assets[file["path"]] = media_type
    return assets


def _get_resources_links(
    metadata: dict, **context: Unpack[STACContext]
) -> list[tuple[str, str]]:
    _metadata_resources = metadata.get("resources", {})
    return _retrieve_resources_links(_metadata_resources, **context)


def _retrieve_resources_links(
    mapping: dict, labels: list | None = None, **context: Unpack[STACContext]
) -> list[tuple[str, str]]:
    links = []
    labels = labels if labels is not None else []

    for key, val in mapping.items():
        if isinstance(val, dict):
            links.extend(_retrieve_resources_links(val, [key, *labels], **context))
        elif isinstance(val, list):
            for raw_link in val:
                links.append(_parse_resource_link(raw_link, key, labels, **context))
        elif isinstance(val, str):
            links.append(_parse_resource_link(val, key, labels, **context))
    return links


def _parse_resource_link(
    raw_link: str, key: str, labels: list, **context: Unpack[STACContext]
) -> tuple[str, str, list[str]]:
    _request = context["request"]
    _token = context["token"]

    split_link = raw_link.split("::")
    if len(split_link) >= 2:
        link_labels = split_link[0].split(",")
        link = split_link[1]
    else:
        link_labels = []
        link = split_link[0]

    _labels = [*labels, *link_labels]

    if "stac" in _labels:
        path = parse.urlparse(link).path.removeprefix("/")
        link = url_for(
            _request,
            "stac2_collection_feature",
            path=dict(
                collection_id=key,
                feature_id=path,
            ),
            query={**_token.query},
        )
        _labels.append(key)
        title = f"{key}: {path}"
    else:
        title = key

    return title, link, _labels


def _get_sharinghub_properties(category: Category, metadata: dict) -> dict:
    return category.get("features", {}) | metadata.get("sharinghub", {})


def _get_scientific_citations(
    metadata: dict, md_content: str
) -> tuple[tuple[str | None, str | None], list[tuple[str | None, str | None]]]:
    DOI_PREFIX = "DOI:"

    doi_link = None
    doi_citation = None
    doi_publications = []

    if "doi" in metadata:
        doi = metadata["doi"]
        if isinstance(doi, str):
            doi_link = doi
        elif isinstance(doi, dict):
            doi_link = doi.get("link")
            doi_citation = doi.get("citation")

    for link_text, link_href in md.get_links(md_content):
        if link_href.startswith("https://doi.org"):
            if link_text.startswith(DOI_PREFIX):
                doi_link = link_href
                doi_citation = link_text.removeprefix(DOI_PREFIX).lstrip()
            else:
                doi_publications.append((link_href, link_text))

    if "publications" in metadata:
        for _doi_publication in metadata["publications"]:
            doi_publications.append(
                (_doi_publication.get("link"), _doi_publication.get("citation"))
            )

    return (doi_link, doi_citation), doi_publications


def _get_machine_learning(
    metadata: dict, resources_links: list[tuple[str, str, list[str]]]
) -> tuple[
    dict[str, str],
    dict[str, list[str] | EllipsisType],
    dict[str, tuple[str, list[tuple[str, str]]]],
]:
    ml_metadata = metadata.get("ml", {})

    ml_properties = {}
    ml_assets = {}
    ml_links = {
        "inferencing-image": ("docker-image", []),
        "training-image": ("docker-image", []),
        "train-data": ("application/json", []),
        "test-data": ("application/json", []),
    }

    properties = [
        "learning_approach",
        "prediction_type",
        "architecture",
    ]
    training_properties = [
        "os",
        "processor-type",
    ]
    for prop in properties:
        if val := ml_metadata.get(prop.replace("_", "-")):
            ml_properties[prop] = val
    for prop in training_properties:
        if val := ml_metadata.get("training", {}).get(prop):
            ml_properties[f"training-{prop}"] = val

    if ml_properties:
        ml_properties["type"] = "ml-model"

    inference = ml_metadata.get("inference", {})
    training = ml_metadata.get("training", {})

    inference_images = inference.get("images", {})
    training_images = training.get("images", {})
    for image_title, image in inference_images.items():
        ml_links["inferencing-image"][1].append((f"{image_title}: {image}", image))
    for image_title, image in training_images.items():
        ml_links["training-image"][1].append((f"{image_title}: {image}", image))

    for rc_title, rc_link, rc_labels in resources_links:
        if "stac" in rc_labels:
            if "ml-train" in rc_labels:
                ml_links["train-data"][1].append((rc_title, rc_link))
            if "ml-test" in rc_labels:
                ml_links["test-data"][1].append((rc_title, rc_link))

    ml_assets["checkpoint"] = _retrieve_elements(
        ml_metadata, "checkpoint", "checkpoints"
    )
    ml_assets["inference-runtime"] = _retrieve_elements(
        inference, "runtime", "runtimes"
    )
    ml_assets["training-runtime"] = _retrieve_elements(training, "runtime", "runtimes")

    return ml_properties, ml_assets, ml_links


def _retrieve_elements(mapping: dict, singular: str, plural: str) -> list:
    element = mapping.get(singular, ...)
    elements = mapping.get(plural, ...)
    if isinstance(elements, list):
        return elements
    elif isinstance(element, str):
        return [element]
    elif all((element, elements)):
        return ...
    return []


def _get_file_asset_id(file_path: str) -> str:
    return f"{FILE_ASSET_PREFIX}{file_path}"


def _get_project_stac_id(project: GitlabProject, category: Category | None) -> str:
    if not category:
        category = get_project_category(project)
    return f"{category['id']}-{project['id']}"


def _parse_project_stac_id(stac_id: str) -> tuple[Category, int] | None:
    try:
        category_id, project_id_str = stac_id.rsplit("-", 1)
        category = get_category(category_id)
        project_id = int(project_id_str)
        if category:
            return category, project_id
    except ValueError:
        pass
    return None
