import logging
import mimetypes
import os
import re
from datetime import datetime as dt
from pathlib import Path
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
from app.utils import geo
from app.utils import markdown as md
from app.utils.http import is_local, url_for

from ..settings import STAC_PROJECTS_CACHE_TIMEOUT
from .category import Category, FeatureVal, get_category

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

DOI_URL = "https://doi.org/"


class STACSearchQuery(BaseModel):
    limit: Annotated[int, Field(strict=True, gt=0)] = 10
    sortby: str | None = Field(default=None)
    bbox: list[float] = Field(default_factory=list)
    datetime: str | None = Field(default=None)
    intersects: Json = Field(default=None)
    ids: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    q: list[str] = Field(default_factory=list)

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
                "stac_collection",
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
                    "stac_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_root",
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
                    "stac_conformance",
                    query={**_token.query},
                ),
            },
            {
                "rel": "data",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_collections",
                    query={**_token.query},
                ),
            },
            {
                "rel": "search",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    "stac_search",
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
                    "stac_collections",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_root",
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
                    "stac_collection",
                    path=dict(collection_id=category.id),
                    query={**_token.query},
                ),
            },
            {
                "rel": "parent",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "root",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_root",
                    query={**_token.query},
                ),
            },
            {
                "rel": "items",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    "stac_collection_items",
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
                    "stac_collection",
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
                    "stac_root",
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
    readme_doc, metadata = md.parse(readme)

    # Metadata parsing

    description = _get_preview_description(project, readme_doc)
    keywords = _get_tags(project)
    preview = _retrieve_preview(readme_doc, metadata)
    spatial_extent, temporal_extent = _retrieve_extent(project, metadata)

    # STAC generation
    default_fields, default_links, default_assets = _build_stac_item_default_values(
        project, preview, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": get_project_stac_id(project),
        **(
            {
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
            }
            if spatial_extent
            else {"geometry": None}
        ),
        **default_fields,
        "properties": {
            "title": project.name,
            "description": description,
            "datetime": temporal_extent[1],
            "created": temporal_extent[0],
            "updated": temporal_extent[1],
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

    readme_doc, metadata = md.parse(readme)

    # Metadata parsing

    description = _get_description(project, readme_doc, **context)
    keywords = _get_tags(project)
    preview = _retrieve_preview(readme_doc, metadata)
    license_id, license_url = _retrieve_license(
        project, metadata
    )  # "license" property can be mapped transparently
    spatial_extent, temporal_extent = _retrieve_extent(project, metadata)
    providers = _retrieve_providers(project, metadata)
    files_assets = _retrieve_files_assets(files, metadata, assets_rules)
    related_links = _retrieve_related_links(metadata)

    sharinghub_properties = _retrieve_sharinghub_properties(project, files, metadata)

    raw_links = metadata.pop("links", [])
    raw_assets = metadata.pop("assets", {})

    if not isinstance(raw_links, list):
        raw_links = []
    if not isinstance(raw_assets, dict):
        raw_assets = {}

    # STAC generation

    stac_extensions, extensions = _retrieve_extensions(readme_doc, metadata, **context)

    stac_properties = {**metadata}
    stac_assets = {**raw_assets}
    stac_links = [*raw_links]

    if license_id:
        stac_properties["license"] = license_id
    if license_url:
        stac_links.append(
            {
                "rel": "license",
                "href": license_url,
            }
        )

    for file_path, file_media_type in files_assets.items():
        stac_assets[file_path] = {
            "href": file_path,
            "title": file_path,
            "roles": ["data"],
        }
        if file_media_type:
            stac_assets[file_path]["type"] = file_media_type

    for category_id, related_project_url in related_links:
        _path = parse.urlparse(related_project_url).path.removeprefix("/")
        stac_links.append(
            {
                "rel": "derived_from",
                "type": "application/geo+json",
                "title": f"{category_id}: {_path}",
                "href": url_for(
                    _request,
                    "stac_collection_feature",
                    path=dict(
                        collection_id=category_id,
                        feature_id=_path,
                    ),
                    query={**_token.query},
                ),
            }
        )

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
        stac_assets["release"] = {
            "href": archive_url,
            "title": f"Release {release.tag}: {release.name}",
            "roles": ["source"],
        }
        if release.description:
            stac_assets["release"]["description"] = release.description
        if media_type:
            stac_assets["release"]["type"] = media_type

    for ext_name, ext_properties in extensions.items():
        for property, val in ext_properties.items():
            stac_properties[f"{ext_name}:{property}"] = val

    if doi := stac_properties.get("sci:doi"):
        stac_links.append({"rel": "cite-as", "href": f"{DOI_URL}{doi}"})

    if sharinghub_properties:
        for prop, val in sharinghub_properties.items():
            stac_properties[f"sharinghub:{prop}"] = val

    for link in stac_links:
        link["href"] = _resolve_href(link["href"], project, **context)

    for asset in stac_assets.values():
        asset["href"] = _resolve_href(asset["href"], project, **context)

    default_fields, default_links, default_assets = _build_stac_item_default_values(
        project, preview, **context
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": stac_extensions,
        "type": "Feature",
        "id": get_project_stac_id(project),
        **(
            {
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
            }
            if spatial_extent
            else {"geometry": None}
        ),
        **default_fields,
        "properties": {
            "title": project.name,
            "description": description,
            "datetime": project.last_update,
            "start_datetime": temporal_extent[0],
            "end_datetime": temporal_extent[1],
            "created": temporal_extent[0],
            "updated": temporal_extent[1],
            "keywords": keywords,
            "providers": providers,
            **stac_properties,
        },
        "links": [
            *default_links,
            {
                "rel": "bug_tracker",
                "type": "text/html",
                "href": project.issues_url,
                "title": "Issues",
            },
            *stac_links,
        ],
        "assets": default_assets | stac_assets,
    }


def _build_stac_item_default_values(
    project: Project,
    preview: str | None,
    **context: Unpack[STACContext],
) -> tuple[dict[str, str], list[dict], dict[str, dict]]:
    _request = context["request"]
    _token = context["token"]

    fields = {}
    assets = {}
    links = [
        {
            "rel": "self",
            "type": "application/geo+json",
            "href": url_for(
                _request,
                "stac_collection_feature",
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
                "stac_collection",
                path=dict(collection_id=project.category.id),
                query={**_token.query},
            ),
        },
        {
            "rel": "root",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_root",
                query={**_token.query},
            ),
        },
    ]

    if project.category:
        fields["collection"] = project.category.id
        links.append(
            {
                "rel": "collection",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_collection",
                    path=dict(collection_id=project.category.id),
                    query={**_token.query},
                ),
            }
        )

    if preview:
        preview_href = _resolve_href(
            preview, project, {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)}, **context
        )
        assets["preview"] = {
            "href": preview_href,
            "title": "Preview",
            "roles": ["thumbnail"],
        }
        _preview_path = parse.urlparse(preview).path
        _media_type, _ = mimetypes.guess_type(_preview_path)
        if _media_type:
            assets["preview"]["type"] = _media_type
        links.append(
            {
                "rel": "preview",
                "href": preview_href,
            }
        )
    return fields, links, assets


def _get_preview_description(
    project: Project, md_content: str, wrap_char: int = 150
) -> str:
    description = project.description
    if description:
        description = re.sub(geo.BBOX_PATTERN, "", description).strip()

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
    description = __resolve_links(description, project, **context)
    description = md.clean_new_lines(description)
    return description


def __resolve_links(
    md_content: str, project: Project, **context: Unpack[STACContext]
) -> str:
    _request = context["request"]
    _token = context["token"]

    def _resolve_src(match: re.Match):
        href = match.groupdict()["src"]
        href = _resolve_href(
            href, project, {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)}, **context
        )
        return f'src="{href}"'

    def __resolve_md(match: re.Match):
        image = match.groupdict()
        href = image["src"]
        href = _resolve_href(
            href, project, {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)}, **context
        )
        return f"![{image['alt']}]({href})"

    md_patched = md_content
    md_patched = re.sub(r"src=(\"|')(?P<src>.*?)(\"|')", _resolve_src, md_patched)
    md_patched = re.sub(md.IMAGE_PATTERN, __resolve_md, md_patched)
    return md_patched


def _get_tags(project: Project) -> list[str]:
    project_topics = list(project.topics)
    project_topics.remove(project.category.gitlab_topic)
    return project_topics


def _retrieve_preview(md_content: str, metadata: dict) -> str | None:
    preview = metadata.pop("preview", None)
    for link_alt, link_img in md.get_images(md_content):
        if link_alt.lower().strip() == "preview":
            preview = link_img
    return preview


def _retrieve_license(
    project: Project, metadata: dict
) -> tuple[str | None, str | None]:
    license_id = metadata.pop("license", project.license_id)
    license_url = metadata.pop("license-url", project.license_url)
    if license_url:
        license_url = str(license_url)
    return license_id, license_url


def _retrieve_extent(
    project: Project, metadata: dict
) -> tuple[list[float], list[str | None]]:
    extent = metadata.pop("extent", {})

    if project.description:
        bbox = geo.read_bbox(project.description)
    else:
        bbox = None

    spatial_extent = bbox if bbox else extent.get("bbox")
    temporal_extent = extent.get("temporal", [project.created_at, project.last_update])
    return spatial_extent, temporal_extent


def _retrieve_providers(project: Project, metadata: dict) -> list[dict]:
    providers = metadata.pop("providers", [])

    has_producer = True
    has_host = False
    for provider in providers:
        _roles = provider.get("roles", [])
        if "host" in _roles:
            has_host = True
        if "producer" in _roles:
            has_producer = True

    if not has_host:
        providers.append(
            {
                "name": f"GitLab ({GITLAB_URL})",
                "roles": ["host"],
                "url": project.url,
            }
        )
    if not has_producer:
        producer = project.full_name.split("/")[0].rstrip()
        _producer_path = project.path.split("/")[0]
        producer_url = f"{GITLAB_URL}/{_producer_path}"
        provider.append(
            {
                "name": producer,
                "roles": ["producer"],
                "url": producer_url,
            }
        )

    return providers


def _retrieve_files_assets(
    files: list[str],
    metadata: str,
    assets_rules: list[str],
) -> dict[str, str | None]:
    assets_mapping = __retrieve_assets_mapping(metadata, assets_rules)
    return __get_files_assets(files, assets_mapping)


def __retrieve_assets_mapping(
    metadata: dict,
    assets_rules: list[str],
) -> dict[str, str | None]:
    assets_mapping = {}
    for asset_rule in (*assets_rules, *metadata.pop("files", [])):
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


def __get_files_assets(
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


def _retrieve_related_links(metadata: dict) -> list[tuple[str, str]]:
    links = []
    related = metadata.pop("related", {})
    for category_id, val in related.items():
        if isinstance(val, str):
            links.append((category_id, val))
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str):
                    links.append((category_id, v))
    return links


def _retrieve_sharinghub_properties(
    project: Project, files: list[str], metadata: dict
) -> dict:
    features = project.category.features
    if not [fpath for fpath in files if fpath.startswith(".dvc/")]:
        features["store-s3"] = FeatureVal.DISABLE
    return {
        "id": project.id,
        "name": project.full_name,
        "path": project.path,
        "stars": project.star_count,
        "category": project.category.id,
        **features,
        **metadata.pop("sharinghub", {}),
    }


def _retrieve_extensions(
    readme: str, metadata: dict, **context: Unpack[STACContext]
) -> tuple[list[str], dict]:
    extensions_mapped = {
        "eo": "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
        "label": "https://stac-extensions.github.io/label/v1.0.1/schema.json",
        "sci": "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
        "ml-model": "https://stac-extensions.github.io/ml-model/v1.0.0/schema.json",
    }
    extensions_enabled = set()
    extensions = {}

    for ext_name in extensions_mapped:
        if ext := metadata.pop(ext_name, None):
            extensions_enabled.add(extensions_mapped[ext_name])
            extensions[ext_name] = ext

    if "ml-model" in extensions:
        extensions["ml-model"]["type"] = "ml-model"

    doi, publications = __parse_scientific_citations(readme)
    if any((doi, publications)):
        extensions_enabled.add(extensions_mapped["sci"])
        extensions["sci"] = {}
        if doi:
            extensions["sci"]["doi"], extensions["sci"]["citation"] = doi
        if publications:
            extensions["sci"]["publications"] = publications

    return list(extensions_enabled), extensions


def __parse_scientific_citations(
    md_content: str,
) -> tuple[tuple[str, str] | None, list[tuple[str, str]]]:
    DOI_PREFIX = "DOI:"

    doi = None
    publications = []

    for link_text, link_href in md.get_links(md_content):
        if link_href.startswith(DOI_URL):
            _doi = link_href.removeprefix(DOI_URL)
            if link_text.startswith(DOI_PREFIX):
                doi = (_doi, link_text.removeprefix(DOI_PREFIX).lstrip())
            else:
                publications.append((_doi, link_text))

    return doi, publications


def _resolve_href(
    href: str,
    project: Project,
    query: dict | None = None,
    **context: Unpack[STACContext],
) -> str:
    _request = context["request"]
    _token = context["token"]

    if is_local(href):
        path = os.path.relpath(href, start="/" if os.path.isabs(href) else None)
        href_query = {"ref": project.default_branch}
        if query:
            href_query |= query
        href = url_for(
            _request,
            "download_gitlab_file",
            path=dict(
                project_path=project.path,
                file_path=path,
            ),
            query={**href_query, **_token.rc_query},
        )
    elif match := re.search(
        r"(?P<collection>[a-z\-]+)\+(?P<href>http[s]?://[^)]+)", href
    ):
        _map = match.groupdict()
        collection = _map["collection"]
        href_parsed = parse.urlparse(_map["href"])
        href_query = dict(parse.parse_qsl(href_parsed.query))
        if query:
            href_query |= query
        href = url_for(
            _request,
            "stac_collection_feature",
            path=dict(
                collection_id=collection,
                feature_id=href_parsed.path.removeprefix("/"),
            ),
            query={**href_query, **_token.query},
        )
    return href
