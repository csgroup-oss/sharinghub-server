import mimetypes
import os
import re
from pathlib import Path
from types import EllipsisType
from typing import Any, NotRequired, TypeAlias, TypedDict, Unpack
from urllib import parse

from fastapi import Request

from app.api.gitlab import (
    GITLAB_LICENSES_SPDX_MAPPING,
    GitlabProject,
    GitlabProjectFile,
    GitlabProjectRelease,
    project_issues_url,
    project_url,
)
from app.config import GITLAB_URL, STAC_ROOT_CONF
from app.dependencies import GitlabToken
from app.utils import markdown as md
from app.utils.http import is_local, slugify, url_for

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


class STACContext(TypedDict):
    request: Request
    token: GitlabToken


class CategoryFields(TypedDict):
    title: str
    description: NotRequired[str]
    preview: NotRequired[str]
    gitlab_topic: NotRequired[str]
    features: TypedDict


class Category(CategoryFields):
    name: str


CategorySpec: TypeAlias = dict[str, CategoryFields]


def build_stac_search_result(
    features: list[dict],
    page: int,
    limit: int,
    search_query: dict[str, Any],
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    page_features = features[(page - 1) * limit : page * limit]
    count_matched = len(features)
    count_returned = len(page_features)

    query_params = search_query | dict(_request.query_params)
    nav_links = []
    if page > 1:
        prev_params = query_params.copy()
        prev_params["page"] = page - 1
        prev_url = url_for(
            _request,
            "stac_search",
            query=prev_params,
        )
        nav_links.append(
            {
                "rel": "prev",
                "href": prev_url,
                "type": "application/geo+json",
            }
        )

        first_params = query_params.copy()
        first_params["page"] = 1
        first_url = url_for(
            _request,
            "stac_search",
            query=first_params,
        )
        nav_links.append(
            {
                "rel": "first",
                "href": first_url,
                "type": "application/geo+json",
            }
        )

    if features[page * limit :]:
        next_params = query_params.copy()
        next_params["page"] = page + 1
        next_url = url_for(
            _request,
            "stac_search",
            query=next_params,
        )
        nav_links.append(
            {
                "rel": "next",
                "href": next_url,
                "type": "application/geo+json",
            }
        )

        last_params = query_params.copy()
        last_params["page"] = len(features) // limit + len(features) % limit
        last_url = url_for(
            _request,
            "stac_search",
            query=last_params,
        )
        nav_links.append(
            {
                "rel": "last",
                "href": last_url,
                "type": "application/geo+json",
            }
        )

    return {
        "stac_version": "1.0.0",
        "type": "FeatureCollection",
        "id": url_for(
            _request,
            "stac_search",
            query={**_token.query},
        ),
        "context": {
            "limit": limit,
            "matched": count_matched,
            "returned": count_returned,
        },
        "numberMatched": count_matched,
        "numberReturned": count_returned,
        "features": page_features,
        "links": [
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
                "rel": "self",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_search",
                    query=query_params,
                ),
            },
            *nav_links,
        ],
    }


def build_stac_root(categories: CategorySpec, **context: Unpack[STACContext]) -> dict:
    _request = context["request"]
    _token = context["token"]

    title = STAC_ROOT_CONF.get("title", "GitLab STAC")
    description = STAC_ROOT_CONF.get(
        "description",
        f"Catalog generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHUB.",
    )
    logo = STAC_ROOT_CONF.get("logo")

    links = [
        {
            "rel": "child",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_category",
                path=dict(category=category_name),
                query={**_token.query},
            ),
        }
        for category_name in categories
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
        "id": STAC_ROOT_CONF["id"],
        "title": title,
        "description": description,
        "links": [
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
                "rel": "self",
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
                "href": url_for(_request, "index") + "docs",
                "title": "OpenAPI interactive docs: Swagger UI",
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
                "title": "STAC Search (GET)",
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
                "title": "STAC Search (POST)",
            },
            *links,
        ],
        "conformsTo": [
            "https://api.stacspec.org/v1.0.0/core",
            "https://api.stacspec.org/v1.0.0/item-search",
            "https://api.stacspec.org/v1.0.0-rc.1/item-search#free-text",
            "https://api.stacspec.org/v1.0.0-rc.1/item-search#advanced-free-text",
            "https://api.stacspec.org/v1.0.0-rc.1/ogcapi-features",
            "https://api.stacspec.org/v1.0.0-rc.1/ogcapi-features#free-text",
            "https://api.stacspec.org/v1.0.0-rc.1/ogcapi-features#advanced-free-text",
        ],
    }


def build_stac_category(
    category: Category,
    projects: list[GitlabProject],
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    title = category["title"]
    description = category.get(
        "description",
        f"STAC {title} generated from your [Gitlab]({GITLAB_URL}) repositories with SharingHUB.",
    )
    logo = category.get("logo")

    links = [
        {
            "rel": "child",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_project",
                path=dict(
                    category=category["name"],
                    project_path=project["path_with_namespace"],
                ),
                query={**_token.query},
            ),
        }
        for project in projects
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

    stac_id = f"{STAC_ROOT_CONF['id']}-{slugify(category['name'])}"
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": stac_id,
        "title": title,
        "description": description,
        "links": [
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
                "rel": "self",
                "type": "application/json",
                "href": url_for(
                    _request,
                    "stac_category",
                    path=dict(category=category["name"]),
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
            *links,
        ],
    }


def build_stac_for_project(
    category: Category,
    project: GitlabProject,
    readme: str,
    files: list[GitlabProjectFile],
    assets_rules: list[str],
    release: GitlabProjectRelease | None,
    release_source_format: str,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _token = context["token"]

    readme_doc, readme_metadata = md.parse(readme)
    assets_mapping = _get_assets_mapping(assets_rules, readme_metadata)

    # STAC data

    stac_id = f"{STAC_ROOT_CONF['id']}-{slugify(category['name'])}-{project['id']}"
    title = project["name"]
    description = _resolve_images(
        md.increase_headings(readme_doc, 3), project, **context
    )
    keywords = _get_keywords(category, project, readme_metadata)
    preview, preview_media_type = _get_preview(readme_metadata, readme_doc)
    license, license_url = _get_license(project, readme_metadata)
    producer, producer_url = _get_producer(project, readme_metadata)
    spatial_extent, temporal_extent = _get_extent(project, readme_metadata)
    files_assets = _get_files_assets(files, assets_mapping)
    resources_links = _get_resources_links(readme_metadata, **context)

    ## Extensions

    ### Scientific Citation extension (https://github.com/stac-extensions/scientific)
    doi, doi_publications = _get_scientific_citations(readme_metadata, readme_doc)
    doi_link, doi_citation = doi

    ### ML Model Extension Specification (https://github.com/stac-extensions/ml-model)
    ml_properties, ml_assets, ml_links = _get_machine_learning(
        readme_metadata, resources_links
    )
    ## sharing hub extensions
    sharinghub_properties = _get_sharinghub_properties(category, readme_metadata)

    # STAC generation

    stac_extensions = [
        "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
    ]

    fields = {}
    assets = {}
    links = [
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
            "rel": "self",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_project",
                path=dict(
                    category=category["name"],
                    project_path=project["path_with_namespace"],
                ),
                query={**_token.query},
            ),
        },
        {
            "rel": "parent",
            "type": "application/json",
            "href": url_for(
                _request,
                "stac_category",
                path=dict(category=category["name"]),
                query={**_token.query},
            ),
        },
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
    ]
    providers = [
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
    ]

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

    if license_url:
        links.append(
            {
                "rel": "license",
                "href": license_url,
            }
        )

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

    if license:
        fields["license"] = license

    return {
        "stac_version": "1.0.0",
        "stac_extensions": stac_extensions,
        "type": "Feature",
        "id": stac_id,
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
            "title": title,
            "description": description,
            "datetime": None,
            "start_datetime": temporal_extent[0],
            "end_datetime": temporal_extent[1],
            "created": temporal_extent[0],
            "updated": temporal_extent[1],
            "keywords": keywords,
            "providers": providers,
            "sharinghub:name": project["name_with_namespace"],
            "sharinghub:path": project["path_with_namespace"],
            "sharinghub:id": project["id"],
            "sharinghub:stars": project["star_count"],
            **fields,
        },
        "links": links,
        "assets": assets,
        "collection": None,
    }


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


def _get_keywords(cat: Category, project: GitlabProject, metadata: dict) -> list[str]:
    cat_keyword = slugify(cat["name"])
    namespaces_keywords = [
        slugify(g) for g in project["path_with_namespace"].split("/")[:-1]
    ]
    readme_keywords = metadata.get("keywords", [])
    return list(dict.fromkeys([cat_keyword, *namespaces_keywords, *readme_keywords]))


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


def _get_extent(
    project: GitlabProject, metadata: dict
) -> tuple[list[float], list[str | None]]:
    extent = metadata.get("extent", {})
    spatial_extent = extent.get("bbox", [-180.0, -90.0, 180.0, 90.0])
    temporal_extent = extent.get(
        "temporal", [project["created_at"], project["last_activity_at"]]
    )
    return spatial_extent, temporal_extent


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


def _get_sharinghub_properties(cat: Category, metadata: dict) -> dict:
    return cat.get("features", {}) | metadata.get("sharinghub", {})


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
            "stac_project",
            path=dict(
                category=key,
                project_path=path,
            ),
            query={**_token.query},
        )
        _labels.append(key)
        title = f"{key}: {path}"
    else:
        title = key

    return title, link, _labels


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
