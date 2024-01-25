import logging
import math
import mimetypes
import os
import re
from datetime import datetime as dt
from pathlib import Path
from types import EllipsisType
from typing import Annotated, TypedDict, Unpack
from urllib import parse

from fastapi import Request
from pydantic import (
    BaseModel,
    Field,
    Json,
    SerializationInfo,
    computed_field,
    field_serializer,
    field_validator,
)

from app.auth import GitlabToken
from app.providers.schemas import Project, Release
from app.settings import GITLAB_URL
from app.utils import markdown as md
from app.utils.http import is_local, url_for

from .category import Category, get_category

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


class STACPagination(TypedDict):
    limit: int
    matched: int
    returned: int
    next: str | None
    prev: str | None


class STACContext(TypedDict):
    request: Request
    token: GitlabToken


def get_project_stac_id(project: Project) -> str:
    return f"{project.category.id}-{project.id}"


def parse_project_stac_id(stac_id: str) -> tuple[Category, int] | None:
    try:
        category_id, project_id_str = stac_id.rsplit("-", 1)
        category = get_category(category_id)
        project_id = int(project_id_str)
        if category:
            return category, project_id
    except ValueError:
        pass
    return None


def build_stac_root(
    root_config: dict,
    conformance_classes: list[str],
    categories: list[Category],
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
                path=dict(collection_id=category.id),
                query={**_token.query},
            ),
        }
        for category in categories
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
            "limit": _collections_len,
            "matched": _collections_len,
            "returned": _collections_len,
        },
        "numberMatched": _collections_len,
        "numberReturned": _collections_len,
    }


def build_stac_collection(category: Category, **context: Unpack[STACContext]) -> dict:
    _request = context["request"]
    _token = context["token"]

    title = category.title
    description = (
        category.description
        if category.description
        else f"STAC {title} generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHUB.",
    )
    logo = category.logo

    links = []

    if logo:
        logo_path = Path(logo.path)
        logo_media_type, _ = mimetypes.guess_type(logo_path.name)
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
        "id": category.id,
        "title": title,
        "description": description,
        "license": "proprietary",
        "keywords": [category.id],
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
                    path=dict(collection_id=category.id),
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
                    path=dict(collection_id=category.id),
                    query={**_token.query},
                ),
            },
            *links,
        ],
    }


def build_features_collection(
    features: list[dict],
    pagination: STACPagination,
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
                    path=dict(collection_id=category.id),
                    query={**_token.query},
                ),
            }
        )

    query_params = dict(_request.query_params)

    if pagination["prev"]:
        prev_params = query_params.copy()
        prev_params.pop("next", None)
        prev_params["prev"] = pagination["prev"]
        links.append(
            {
                "rel": "prev",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query=prev_params,
                ),
                "type": "application/geo+json",
            }
        )

    if pagination["next"]:
        next_params = query_params.copy()
        next_params.pop("prev", None)
        next_params["next"] = pagination["next"]
        links.append(
            {
                "rel": "next",
                "href": url_for(
                    _request,
                    route,
                    path=_request.path_params,
                    query=next_params,
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
    project: Project,
    readme: str,
    **context: Unpack[STACContext],
) -> dict:
    readme_doc, readme_metadata = md.parse(readme)

    # STAC data
    description = _get_preview_description(project, readme_doc)
    keywords = _get_tags(project)
    preview, preview_media_type = _get_preview(readme_metadata, readme_doc)
    spatial_extent, _ = get_extent(project, readme_metadata)

    # STAC generation
    default_links, default_assets = get_stac_item_default_links_and_assets(
        project, preview, preview_media_type, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": get_project_stac_id(project),
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
        }
        if spatial_extent
        else None,
        "bbox": spatial_extent,
        "properties": {
            "title": project.name,
            "description": description,
            "datetime": project.last_update,
            "keywords": keywords,
            "sharinghub:stars": project.star_count,
            "sharinghub:category": project.category.id,
        },
        "links": default_links,
        "assets": default_assets,
    }


def build_stac_item(
    project: Project,
    readme: str,
    files: list[str],
    assets_rules: list[str],
    release: Release | None,
    release_source_format: str,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    readme_doc, readme_metadata = md.parse(readme)
    assets_mapping = _get_assets_mapping(assets_rules, readme_metadata)

    # STAC data

    description = _get_description(project, readme_doc, **context)
    keywords = _get_tags(project)
    preview, preview_media_type = _get_preview(readme_metadata, readme_doc)
    license, license_url = _get_license(project, readme_metadata)
    producer, producer_url = _get_producer(project, readme_metadata)
    spatial_extent, temporal_extent = get_extent(project, readme_metadata)
    files_assets = _get_files_assets(files, assets_mapping)
    resources_links = _get_resources_links(readme_metadata, **context)

    # _ Extensions

    # __ sharing hub extensions
    sharinghub_properties = _get_sharinghub_properties(
        project.category, readme_metadata
    )

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
                    project_path=project.path,
                    file_path=file_path,
                ),
                query={"ref": project.default_branch, **_token.rc_query},
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
                project_path=project.path,
                format=release_source_format,
            ),
            query={"ref": release.tag, **_token.rc_query},
        )
        media_type, _ = mimetypes.guess_type(f"archive.{release_source_format}")
        assets["release"] = {
            "href": archive_url,
            "title": f"Release {release.tag}: {release.name}",
            "roles": ["source"],
        }
        if release.description:
            assets["release"]["description"] = release.description
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
        project, preview, preview_media_type, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": stac_extensions,
        "type": "Feature",
        "id": get_project_stac_id(project),
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
        }
        if spatial_extent
        else None,
        "bbox": spatial_extent,
        "properties": {
            "title": project.name,
            "description": description,
            "datetime": project.last_update,
            "start_datetime": temporal_extent[0],
            "end_datetime": temporal_extent[1],
            "created": temporal_extent[0],
            "updated": temporal_extent[1],
            "keywords": keywords,
            "providers": [
                {
                    "name": f"GitLab ({GITLAB_URL})",
                    "roles": ["host"],
                    "url": project.url,
                },
                {
                    "name": producer,
                    "roles": ["producer"],
                    "url": producer_url,
                },
            ],
            **fields,
            "sharinghub:name": project.full_name,
            "sharinghub:path": project.path,
            "sharinghub:id": project.id,
            "sharinghub:stars": project.star_count,
        },
        "links": [
            *default_links,
            {
                "rel": "bug_tracker",
                "type": "text/html",
                "href": project.issues_url,
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
    project: Project,
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
                project_path=project.path,
                file_path=preview,
            ),
            query={"ref": project.default_branch, **_token.rc_query},
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
                    collection_id=project.category.id,
                    feature_id=project.path,
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
                path=dict(collection_id=project.category.id),
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
                path=dict(collection_id=project.category.id),
                query={**_token.query},
            ),
        },
        *links,
    ], assets


def _get_preview_description(
    project: Project, md_content: str, wrap_char: int = 150
) -> str:
    description = project.description
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
    project: Project, md_content: str, **context: Unpack[STACContext]
) -> str:
    description = md.increase_headings(md_content, 3)
    description = _resolve_images(description, project, **context)
    description = md.clean_new_lines(description)
    return description


def _get_tags(project: Project) -> list[str]:
    project_topics = list(project.topics)
    project_topics.remove(project.category.gitlab_topic)
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


def get_extent(
    project: Project, metadata: dict
) -> tuple[list[float], list[str | None]]:
    extent = metadata.get("extent", {})
    spatial_extent = extent.get("bbox")
    temporal_extent = extent.get("temporal", [project.created_at, project.last_update])
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
    md_content: str, project: Project, **context: Unpack[STACContext]
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
                    project_path=project.path,
                    file_path=path,
                ),
                query={"ref": project.default_branch, **_token.rc_query},
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
                    project_path=project.path,
                    file_path=path,
                ),
                query={"ref": project.default_branch, **_token.rc_query},
            )
        return f"![{image['alt']}]({url})"

    md_patched = md_content
    md_patched = re.sub(r"src=(\"|')(?P<src>.*?)(\"|')", _resolve_src, md_patched)
    md_patched = re.sub(md.IMAGE_PATTERN, __resolve_md, md_patched)
    return md_patched


def _get_license(project: Project, metadata: dict) -> tuple[str | None, str | None]:
    if "license" in metadata:
        # Must be SPDX identifier: https://spdx.org/licenses/
        license = metadata["license"]
        license_url = None
    elif project.license_id:
        license = project.license_id
        license_url = project.license_url if project.license_url else None
    else:
        # Private
        license = None
        license_url = None
    return license, license_url


def _get_producer(project: Project, metadata: dict) -> tuple[str, str]:
    producer = project.full_name.split("/")[0].rstrip()
    producer = metadata.get("producer", producer)
    _producer_path = project.path.split("/")[0]
    producer_url = f"{GITLAB_URL}/{_producer_path}"
    producer_url = metadata.get("producer_url", producer_url)
    return producer, producer_url


def _get_files_assets(
    files: list[str], assets_mapping: dict[str, str | None]
) -> dict[str, str | None]:
    assets = {}
    for file in files:
        fpath = Path(file)
        for glob in assets_mapping:
            if fpath.match(glob):
                if assets_mapping[glob]:
                    media_type = assets_mapping[glob]
                else:
                    media_type, _ = mimetypes.guess_type(fpath)
                if media_type or not assets.get(file):
                    assets[file] = media_type
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
    return category.features | metadata.get("sharinghub", {})


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
