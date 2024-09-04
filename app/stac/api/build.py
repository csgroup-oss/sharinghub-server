# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, TypedDict, Unpack, cast
from urllib import parse

from fastapi import Request
from shapely.geometry.base import BaseGeometry

from app.auth import GitlabToken
from app.providers.schemas import License, Project, ProjectPreview, ProjectReference
from app.settings import GITLAB_URL
from app.stac.settings import (
    STAC_EXTENSIONS,
    STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
    STAC_PROJECTS_CACHE_TIMEOUT,
)
from app.utils import geo
from app.utils import markdown as md
from app.utils.http import is_local, url_for, urlsafe_path

from .category import Category, FeatureVal
from .search import STACPagination

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

DOI_URL_PATTERN = re.compile(r"https://doi.org/(?P<doi>10\.\d{4,9}/[-._;/:a-zA-Z0-9]+)")
DOI_URL = "https://doi.org/"
DOI_PREFIX = "DOI:"


class STACContext(TypedDict):
    request: Request
    token: GitlabToken


def get_project_stac_id(project: ProjectReference) -> str:
    return project.path


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
        f"Catalog generated from your [Gitlab]({GITLAB_URL}) with SharingHub.",
    )
    logo = root_config.get("logo")

    links = [
        {
            "rel": "child",
            "type": "application/geo+json",
            "href": url_for(
                _request,
                "stac_collection",
                path={"collection_id": category.id},
                query={**_token.query},
            ),
        }
        for category in categories
    ]

    if logo:
        logo_link = {
            "rel": "preview",
            "href": logo,
        }

        logo_media_type, _ = mimetypes.guess_type(logo)
        if logo_media_type:
            logo_link["type"] = logo_media_type

        links.append(logo_link)

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
                    "stac_search_get",
                    query={**_token.query},
                ),
                "method": "GET",
            },
            {
                "rel": "search",
                "type": "application/geo+json",
                "href": url_for(
                    _request,
                    "stac_search_post",
                    query={**_token.query},
                ),
                "method": "POST",
            },
            *links,
        ],
        "conformsTo": conformance_classes,
    }


def build_stac_collections(
    categories: list[Category],
    **context: Unpack[STACContext],
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
        else f"STAC {title} generated from your [Gitlab]({GITLAB_URL}) with SharingHub."
    )
    logo = category.logo

    links = []

    if logo and logo.path:
        logo_path = Path(logo.path)
        logo_media_type, _ = mimetypes.guess_type(logo_path.name)
        links.append(
            {
                "rel": "preview",
                "type": logo_media_type,
                "href": logo,
            },
        )

    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Collection",
        "id": category.id,
        "title": title,
        "description": description,
        "license": "other",
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
                    path={"collection_id": category.id},
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
                    path={"collection_id": category.id},
                    query={**_token.query},
                ),
            },
            *links,
        ],
    }


def build_features_collection(
    features: list[dict],
    state_query: dict[str, Any],
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
                    path={"collection_id": category.id},
                    query={**_token.query},
                ),
            },
        )

    query_params = state_query | dict(_request.query_params)

    if pagination["prev"]:
        prev_params = query_params.copy()
        prev_params.pop("after", None)
        prev_params["before"] = pagination["prev"]
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
            },
        )

    if pagination["next"]:
        next_params = query_params.copy()
        next_params.pop("before", None)
        next_params["after"] = pagination["next"]
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
            },
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


def build_stac_item_reference(
    project: ProjectReference,
    category: Category,
    **context: Unpack[STACContext],
) -> dict:
    default_fields, default_links, default_assets = _build_stac_item_default_values(
        project,
        category,
        **context,
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": get_project_stac_id(project),
        "geometry": None,
        **default_fields,
        "properties": {
            "title": project.name,
            "datetime": None,
        },
        "links": default_links,
        "assets": default_assets,
    }


def build_stac_item_preview(
    project: ProjectPreview,
    category: Category,
    **context: Unpack[STACContext],
) -> dict:
    metadata = {**project.metadata}

    keywords = _get_tags(project)
    preview = _retrieve_preview(project, metadata, **context)
    description = _get_preview_description(project)

    stac_fields, stac_links, stac_assets = _build_stac_item_default_values(
        project,
        category,
        **context,
    )

    if preview:
        stac_links.append(preview[0])
        stac_assets["preview"] = preview[1]

    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": get_project_stac_id(project),
        "geometry": None,
        **stac_fields,
        "properties": {
            "title": project.name,
            "description": description,
            "datetime": project.last_update,
            "keywords": keywords,
            "sharinghub:stars": project.star_count,
        },
        "links": stac_links,
        "assets": stac_assets,
    }


def build_stac_item(
    project: Project,
    category: Category,
    **context: Unpack[STACContext],
) -> dict:
    metadata = {**project.metadata}

    keywords = _get_tags(project)
    preview = _retrieve_preview(project, metadata, **context)
    description = _get_description(project, **context)
    license_ = _retrieve_license(
        project,
        metadata,
    )  # "license" property can be mapped transparently
    spatial_extent, temporal_extent = _retrieve_extent(project, metadata)
    providers = _retrieve_providers(project, metadata)

    # STAC generation

    sharinghub_properties = _retrieve_sharinghub_properties(project, category, metadata)
    stac_extensions, extensions_properties = _retrieve_extensions(project, metadata)

    stac_links = _retrieve_links(project, metadata, **context)
    stac_assets = _retrieve_assets(project, metadata, **context)
    stac_properties = {**metadata, **extensions_properties, **sharinghub_properties}

    if preview:
        stac_links.append(preview[0])
        stac_assets["preview"] = preview[1]

    if license_:
        stac_properties["license"] = license_.id
        stac_links.append(
            {
                "rel": "license",
                "href": license_.url,
            },
        )

    if project.mlflow:
        stac_links.append(
            {
                "rel": "mlflow:tracking-uri",
                "href": project.mlflow.tracking_uri,
                "title": "MLflow - Tracking URI",
            },
        )
        for rm in project.mlflow.registered_models:
            model_url = (
                f"{project.mlflow.tracking_uri}#/models/"
                f"{urlsafe_path(rm.name)}/versions/{rm.latest_version}"
            )
            model_uri = rm.mlflow_uri
            model_name = rm.name.removesuffix(f"({project.id})").rstrip()
            stac_links.append(
                {
                    "rel": "mlflow:model",
                    "href": model_url,
                    "title": f"{model_name} v{rm.latest_version}",
                    "mlflow:uri": model_uri,
                }
            )

    if doi := extensions_properties.get("sci:doi"):
        stac_links.append({"rel": "cite-as", "href": f"{DOI_URL}{doi}"})

    default_fields, default_links, default_assets = _build_stac_item_default_values(
        project,
        category,
        **context,
    )
    return {
        "stac_version": "1.0.0",
        "stac_extensions": stac_extensions,
        "type": "Feature",
        "id": get_project_stac_id(project),
        **(
            {
                "geometry": geo.get_geojson_geometry(spatial_extent),
                "bbox": spatial_extent.bounds,
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
                "href": project.bug_tracker,
                "title": "Bug Tracker",
            },
            *stac_links,
        ],
        "assets": default_assets | stac_assets,
    }


def _build_stac_item_default_values(
    project: ProjectReference,
    category: Category,
    **context: Unpack[STACContext],
) -> tuple[dict[str, str], list[dict], dict[str, dict]]:
    _request = context["request"]
    _token = context["token"]

    fields = {"collection": category.id}
    assets: dict[str, dict] = {}
    links = [
        {
            "rel": "self",
            "type": "application/geo+json",
            "href": url_for(
                _request,
                "stac_collection_feature",
                path={
                    "collection_id": category.id,
                    "feature_id": project.path,
                },
                query={**_token.query},
            ),
        },
        {
            "rel": "parent",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_collection",
                path={"collection_id": category.id},
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
            "rel": "collection",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_collection",
                path={"collection_id": category.id},
                query={**_token.query},
            ),
        },
    ]

    return fields, links, assets


def _get_tags(project: ProjectReference) -> list[str]:
    project_topics = list(project.topics)
    for category in project.categories:
        project_topics.remove(category.gitlab_topic)
    return project_topics


def _get_preview_description(project: ProjectPreview, wrap_char: int = 150) -> str:
    description = project.description

    if not description:
        description = project.readme
        description = md.remove_everything_before_first_heading(description)
        description = md.remove_headings(description)
        description = md.remove_images(description)
        description = md.remove_links(description)
        description = md.clean_new_lines(description)
        description = description[:wrap_char].strip()
        if len(description) == wrap_char:
            description += "..."
    return description if description else ""


def _retrieve_preview(
    project: ProjectPreview,
    metadata: dict,
    **context: Unpack[STACContext],
) -> tuple[dict, dict] | None:
    preview = metadata.pop("preview", None)
    for link_alt, link_img in md.get_images(project.readme):
        if link_alt.lower().strip() == "preview":
            preview = link_img

    if preview:
        preview_href = __resolve_href(
            preview,
            project,
            {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)},
            **context,
        )
        asset = {
            "href": preview_href,
            "title": "Preview",
            "roles": ["thumbnail"],
        }
        _preview_path = parse.urlparse(preview).path
        _media_type, _ = mimetypes.guess_type(_preview_path)
        if _media_type:
            asset["type"] = _media_type
        link = {
            "rel": "preview",
            "href": preview_href,
        }
        return link, asset

    return None


def _retrieve_extent(
    project: ProjectPreview,
    metadata: dict,
) -> tuple[BaseGeometry | None, list[str | None]]:
    extent = metadata.pop("extent", {})
    spatial_extent = project.extent
    temporal_extent = extent.get("temporal", [project.created_at, project.last_update])
    return spatial_extent, temporal_extent


def _get_description(project: Project, **context: Unpack[STACContext]) -> str:
    description = __resolve_links(project.readme, project, **context)
    description = md.clean_new_lines(description)
    return description


def _retrieve_license(project: Project, metadata: dict) -> License | None:
    license_id = metadata.pop(
        "license",
        project.license.id if project.license else None,
    )
    license_url = metadata.pop(
        "license-url",
        project.license.url if project.license else None,
    )
    if license_id:
        if license_url:
            license_url = str(license_url)
        else:
            license_url = f"https://spdx.org/licenses/{license_id}.html"
        return License(id=license_id, url=license_url)
    return None


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
            },
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
            },
        )

    return providers


def _retrieve_sharinghub_properties(
    project: Project, category: Category, metadata: dict
) -> dict:
    features = category.features
    dvc_init = FeatureVal.ENABLE
    if project.files and not [
        fpath for fpath in project.files if fpath.startswith(".dvc/")
    ]:
        dvc_init = FeatureVal.DISABLE
    props = {
        "id": project.id,
        "name": project.full_name,
        "path": project.path,
        "stars": project.star_count,
        "default-branch": project.default_branch,
        "access-level": project.access_level,
        "dvc-init": dvc_init,
        **features,
        **metadata.pop("sharinghub", {}),
    }
    return {f"sharinghub:{prop}": val for prop, val in props.items()}


def _retrieve_extensions(
    project: ProjectPreview,
    metadata: dict,
) -> tuple[list[str], dict[str, Any]]:
    extensions = set()
    properties = {}

    _extensions: dict[str, str] = metadata.pop("extensions", {}) | STAC_EXTENSIONS
    for ext_prefix, ext_schema in _extensions.items():
        if ext := metadata.pop(ext_prefix, None):
            extensions.add(ext_schema)
            for prop, val in ext.items():
                properties[f"{ext_prefix}:{prop}"] = val

    doi, publications = __parse_scientific_citations(project.readme)
    if any((doi, publications)):
        extensions.add(
            "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
        )
        if doi:
            properties["sci:doi"], properties["sci:citation"] = doi
        if publications:
            properties["sci:publications"] = publications

    return list(extensions), properties


def __parse_scientific_citations(
    md_content: str,
) -> tuple[tuple[str, str] | None, list[dict[str, str]]]:
    doi = None
    publications: list[dict[str, str]] = []

    for link_text, link_href in md.get_links(md_content):
        if m := DOI_URL_PATTERN.search(link_href):
            _doi = m.groupdict()["doi"]
            _citation = link_text.removeprefix(DOI_PREFIX).lstrip()
            if not doi:
                doi = (_doi, _citation)
            else:
                publications.append({"doi": _doi, "citation": _citation})

    if not doi and (m := DOI_URL_PATTERN.search(md_content)):
        doi = (m.groupdict()["doi"], "")

    return doi, publications


def _retrieve_links(
    project: ProjectPreview,
    metadata: dict,
    **context: Unpack[STACContext],
) -> list[dict]:
    _request = context["request"]
    _token = context["token"]

    links = metadata.pop("links", [])
    if not isinstance(links, list):
        links = []

    for link in links:
        link["href"] = __resolve_href(link["href"], project, **context)

    def _resolve_related_link(collection_id: str, project_url: str) -> dict[str, str]:
        _path = parse.urlparse(project_url).path.removeprefix("/")
        return {
            "rel": "derived_from",
            "type": "application/geo+json",
            "title": f"{collection_id}: {_path}",
            "href": url_for(
                _request,
                "stac_collection_feature",
                path={
                    "collection_id": collection_id,
                    "feature_id": _path,
                },
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
    **context: Unpack[STACContext],
) -> dict[str, dict[str, Any]]:
    assets: dict[str, dict[str, Any]] = {}

    if assets_rules := __retrieve_assets_rules(project, metadata):
        assets |= __create_assets(project, assets_rules, **context)

    if release := __create_release_asset(project, **context):
        assets["release"] = release

    return assets


def __retrieve_assets_rules(
    project: ProjectReference,
    metadata: dict,
) -> list[dict[str, Any]]:
    assets_rules = []

    metadata_assets = metadata.pop("assets", [])
    if not isinstance(metadata_assets, list):
        metadata_assets = []

    for category in project.categories:
        assets_rules.extend(__process_assets_rules(category.assets))
    assets_rules.extend(__process_assets_rules(metadata_assets))

    return assets_rules


def __process_assets_rules(assets_rules_def: list[str | dict]) -> list[dict]:
    assets_rules = []
    for ma in assets_rules_def:
        if isinstance(ma, str):
            assets_rules.append({"glob": ma})
        elif isinstance(ma, dict):
            assets_rules.append(ma)
    return assets_rules


def __create_assets(
    project: Project,
    assets_rules: list[dict[str, Any]],
    **context: Unpack[STACContext],
) -> dict[str, dict[str, Any]]:
    assets = {}

    _files = [Path(file) for file in project.files] if project.files else []
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
    project: ProjectPreview,
    asset_def: dict[str, Any],
    **context: Unpack[STACContext],
) -> tuple[str, dict[str, Any]] | None:
    href = asset_def.get("href")
    path = asset_def.get("path", "")
    key = asset_def.get("key")
    key = key if key else path
    if key and href:
        key = key.replace("{path}", path)
        asset = {
            "href": __resolve_href(href, project, **context),
            "roles": asset_def.get("roles", ["data"]),
        }
        if _title := asset_def.get("title"):
            asset["title"] = _title.replace("{key}", key).replace("{path}", path)
        if _desc := asset_def.get("description"):
            asset["description"] = _desc.replace("{key}", key).replace("{path}", path)

        _type_as = cast(str, asset_def.get("type-as", ""))
        _raw_type = cast(str, asset_def.get("type", ""))
        if _type := MEDIA_TYPES.get(_type_as, _raw_type):
            asset["type"] = _type
        else:
            href_parsed = parse.urlparse(href)
            media_type, _ = mimetypes.guess_type(href_parsed.path)
            if media_type:
                asset["type"] = media_type
        return key, asset
    return None


def __create_release_asset(
    project: Project,
    **context: Unpack[STACContext],
) -> dict[str, Any] | None:
    if project.latest_release:
        _request = context["request"]
        _token = context["token"]

        release = project.latest_release
        archive_url = url_for(
            _request,
            "download_gitlab_archive",
            path={
                "project_path": project.path,
                "archive_format": STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
            },
            query={"ref": release.tag, **_token.rc_query},
        )
        media_type, _ = mimetypes.guess_type(
            f"archive.{STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT}",
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
    return None


def __resolve_links(
    md_content: str,
    project: ProjectPreview,
    **context: Unpack[STACContext],
) -> str:
    def _resolve_src(match: re.Match) -> str:
        href = match.groupdict()["src"]
        href = __resolve_href(
            href,
            project,
            {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)},
            **context,
        )
        return f'src="{href}"'

    def __resolve_md(match: re.Match) -> str:
        image = match.groupdict()
        href = image["src"]
        href = __resolve_href(
            href,
            project,
            {"cache": int(STAC_PROJECTS_CACHE_TIMEOUT)},
            **context,
        )
        return f"![{image['alt']}]({href})"

    md_patched = md_content
    md_patched = re.sub(r"src=(\"|')(?P<src>.*?)(\"|')", _resolve_src, md_patched)
    md_patched = re.sub(md.IMAGE_PATTERN, __resolve_md, md_patched)
    return md_patched


def __resolve_href(
    href: str,
    project: ProjectPreview,
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
            path={
                "project_path": project.path,
                "file_path": path,
            },
            query={**href_query, **_token.rc_query},
        )
    elif match := re.search(
        r"(?P<collection>[a-z\-]+)\+(?P<href>http[s]?://[^)]+)",
        href,
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
            path={
                "collection_id": collection,
                "feature_id": href_parsed.path.removeprefix("/"),
            },
            query={**href_query, **_token.query},
        )
    return href
