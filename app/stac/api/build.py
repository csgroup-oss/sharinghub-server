import logging
import mimetypes
import os
import re
from datetime import datetime as dt
from pathlib import Path
from typing import Annotated, Any, TypedDict, Unpack
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

from ..settings import (
    STAC_EXTENSIONS,
    STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
    STAC_PROJECTS_CACHE_TIMEOUT,
)
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
        f"Catalog generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHub.",
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
        else f"STAC {title} generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHub.",
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
    release: Release | None,
    **context: Unpack[STACContext],
) -> dict:
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

    # STAC generation

    sharinghub_properties = _retrieve_sharinghub_properties(project, files, metadata)
    stac_extensions, extensions_properties = _retrieve_extensions(readme_doc, metadata)

    stac_properties = {**metadata, **extensions_properties, **sharinghub_properties}
    stac_links = _retrieve_links(project, metadata, **context)
    stac_assets = _retrieve_assets(project, metadata, files, release, **context)

    if license_id:
        stac_properties["license"] = license_id
    if license_url:
        stac_links.append(
            {
                "rel": "license",
                "href": license_url,
            }
        )

    if doi := extensions_properties.get("sci:doi"):
        stac_links.append({"rel": "cite-as", "href": f"{DOI_URL}{doi}"})

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
    elif license_id:
        license_url = f"https://spdx.org/licenses/{license_id}.html"
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

    has_host = False
    has_producer = False
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
        providers.append(
            {
                "name": producer,
                "roles": ["producer"],
                "url": producer_url,
            }
        )

    return providers


def _retrieve_links(
    project: Project, metadata: dict, **context: Unpack[STACContext]
) -> list[tuple[str, str]]:
    _request = context["request"]
    _token = context["token"]

    links = metadata.pop("links", [])
    if not isinstance(links, list):
        links = []

    for link in links:
        link["href"] = _resolve_href(link["href"], project, **context)

    def _resolve_related_link(collection_id: str, project_url: str) -> dict[str, str]:
        _path = parse.urlparse(project_url).path.removeprefix("/")
        return {
            "rel": "derived_from",
            "type": "application/geo+json",
            "title": f"{collection_id}: {_path}",
            "href": url_for(
                _request,
                "stac_collection_feature",
                path=dict(
                    collection_id=collection_id,
                    feature_id=_path,
                ),
                query={**_token.query},
            ),
        }

    for category_id, val in metadata.pop("related", {}).items():
        if isinstance(val, str):
            links.append(_resolve_related_link(category_id, val))
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str):
                    links.append(_resolve_related_link(category_id, v))

    return links


def _retrieve_assets(
    project: Project,
    metadata: dict,
    files: list[str],
    release: Release | None,
    **context: Unpack[STACContext],
) -> dict[str, dict[str, Any]]:
    assets = {}

    if assets_rules := __retrieve_assets_rules(metadata):
        assets |= __create_assets(project, files, assets_rules, **context)

    if release:
        assets["release"] = __create_release_asset(project, release, **context)

    return assets


def __retrieve_assets_rules(metadata: dict) -> list[dict[str, Any]]:
    assets_rules = []

    metadata_assets = metadata.pop("assets", [])
    if not isinstance(metadata_assets, list):
        metadata_assets = []

    for ma in metadata_assets:
        if isinstance(ma, str):
            assets_rules.append({"glob": ma})
        elif isinstance(ma, dict):
            assets_rules.append(ma)

    return assets_rules


def __create_assets(
    project: Project,
    files: list[str],
    assets_rules: list[dict[str, Any]],
    **context: Unpack[STACContext],
) -> dict[str, dict[str, Any]]:
    assets = {}

    _files = [Path(file) for file in files]
    for ar in assets_rules:
        glob = ar.pop("glob", ar.pop("path", None))
        if glob:
            for fpath in _files:
                if fpath.match(glob):
                    a = __prepare_asset(
                        project,
                        {
                            **ar,
                            "key": ar.pop("key", None),
                            "href": str(fpath),
                            "path": str(fpath),
                        },
                        **context,
                    )
                    if a:
                        assets[a[0]] = a[1]
        elif a := __prepare_asset(project, ar, **context):
            assets[a[0]] = a[1]
    return assets


def __prepare_asset(
    project: Project, asset_def: dict[str, Any], **context: Unpack[STACContext]
) -> tuple[str, dict[str, Any]] | None:
    href = asset_def.get("href")
    path = asset_def.get("path", "")
    key = asset_def.get("key")
    key = key if key else path
    if key and href:
        key = key.replace("{path}", path)
        asset = {
            "href": _resolve_href(href, project, **context),
            "roles": asset_def.get("roles", ["data"]),
        }
        if _title := asset_def.get("title"):
            asset["title"] = _title.replace("{key}", key).replace("{path}", path)
        if _desc := asset_def.get("description"):
            asset["description"] = _desc.replace("{key}", key).replace("{path}", path)
        if _type := MEDIA_TYPES.get(asset_def.get("type-as"), asset_def.get("type")):
            asset["type"] = _type
        else:
            href_parsed = parse.urlparse(href)
            media_type, _ = mimetypes.guess_type(href_parsed.path)
            if media_type:
                asset["type"] = media_type
        return key, asset
    return None


def __create_release_asset(
    project: Project, release: Release, **context: Unpack[STACContext]
) -> dict[str, Any]:
    _request = context["request"]
    _token = context["token"]

    archive_url = url_for(
        _request,
        "download_gitlab_archive",
        path=dict(
            project_path=project.path,
            format=STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
        ),
        query={"ref": release.tag, **_token.rc_query},
    )
    media_type, _ = mimetypes.guess_type(
        f"archive.{STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT}"
    )

    release_asset = {
        "href": archive_url,
        "title": f"Release {release.tag}: {release.name}",
        "roles": ["source"],
    }
    if release.description:
        release_asset["description"] = release.description
    if media_type:
        release_asset["type"] = media_type
    return release_asset


def _retrieve_sharinghub_properties(
    project: Project, files: list[str], metadata: dict
) -> dict:
    features = project.category.features
    if not [fpath for fpath in files if fpath.startswith(".dvc/")]:
        features["store-s3"] = FeatureVal.DISABLE
    props = {
        "id": project.id,
        "name": project.full_name,
        "path": project.path,
        "stars": project.star_count,
        "category": project.category.id,
        **features,
        **metadata.pop("sharinghub", {}),
    }
    return {f"sharinghub:{prop}": val for prop, val in props.items()}


def _retrieve_extensions(
    readme: str, metadata: dict
) -> tuple[list[str], dict[str, Any]]:
    extensions = set()
    properties = {}

    _extensions: dict[str, str] = metadata.get("extensions", {}) | STAC_EXTENSIONS
    for ext_prefix, ext_schema in _extensions.items():
        if ext := metadata.get(ext_prefix):
            extensions.add(ext_schema)
            for prop, val in ext.items():
                properties[f"{ext_prefix}:{prop}"] = val

    doi, publications = __parse_scientific_citations(readme)
    if any((doi, publications)):
        extensions.add(
            "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
        )
        if doi:
            properties["sci:doi"], properties["sci:citation"] = doi
        if publications:
            properties["sci:publications"] = publications

    return list(extensions), properties


def __parse_scientific_citations(
    md_content: str,
) -> tuple[tuple[str, str] | None, list[dict[str, str]]]:
    DOI_PREFIX = "DOI:"

    doi = None
    publications = []

    for link_text, link_href in md.get_links(md_content):
        if link_href.startswith(DOI_URL):
            _doi = link_href.removeprefix(DOI_URL)
            if link_text.startswith(DOI_PREFIX):
                doi = (_doi, link_text.removeprefix(DOI_PREFIX).lstrip())
            else:
                publications.append({"doi": _doi, "citation": link_text})

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
