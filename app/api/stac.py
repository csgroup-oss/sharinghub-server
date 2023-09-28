import mimetypes
from pathlib import Path
from types import EllipsisType
from typing import NotRequired, TypeAlias, TypedDict, Unpack
from urllib import parse

from fastapi import Request

from app.api.gitlab import (
    GITLAB_LICENSES_SPDX_MAPPING,
    GitlabPagination,
    GitlabProject,
    GitlabProjectFile,
    GitlabProjectRelease,
    gitlab_url,
    project_issues_url,
    project_url,
)
from app.utils import markdown as md
from app.utils.http import is_local, slugify, url_add_query_params, url_for

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
}

ML_ASSETS_DEFAULT_GLOBS = {
    "inference-runtime": "inferencing.yml",
    "training-runtime": "training.yml",
    "checkpoint": "*.pt",
}

FILE_ASSET_PREFIX = "file://"


class STACContext(TypedDict):
    request: Request
    gitlab_base_uri: str
    token: str


class TopicFields(TypedDict):
    title: str
    description: NotRequired[str]
    preview: NotRequired[str]
    gitlab_name: NotRequired[str]
    default_type: NotRequired[str]


class Topic(TopicFields):
    name: str


TopicSpec: TypeAlias = dict[str, TopicFields]


def get_gitlab_topic(topic: Topic) -> str:
    return topic.get("gitlab_name", topic["name"])


def build_stac_root(
    gitlab_config: dict, topics: TopicSpec, **context: Unpack[STACContext]
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    title = gitlab_config.get("title", "GitLab STAC Catalog")
    description = gitlab_config.get(
        "description",
        f"Catalog generated from your [Gitlab]({_gitlab_url}) repositories with GitLab2STAC.",
    )
    preview = gitlab_config.get("preview")

    links = [
        {
            "rel": "child",
            "href": url_for(
                _request,
                "stac_topic",
                path=dict(
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic_name=topic_name,
                ),
            ),
        }
        for topic_name in topics
    ]

    if preview:
        links.append(
            {
                "rel": "preview",
                "href": preview,
            }
        )

    _gitlab_base_uri_slug = slugify(_gitlab_base_uri).replace("-", "")
    stac_id = f"{_gitlab_base_uri_slug}-catalog"
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": stac_id,
        "title": title,
        "description": description,
        "links": [
            {
                "rel": "root",
                "href": url_for(_request),
            },
            {
                "rel": "self",
                "href": url_for(_request),
            },
            *links,
        ],
    }


def build_stac_topic(
    topic: Topic,
    projects: list[GitlabProject],
    pagination: GitlabPagination,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    title = topic["title"]
    description = topic.get(
        "description",
        f"{title} catalog generated from your [Gitlab]({_gitlab_url}) repositories with GitLab2STAC.",
    )
    preview = topic.get("preview")

    links = [
        {
            "rel": "child",
            "href": url_for(
                _request,
                "stac_project",
                path=dict(
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic_name=topic["name"],
                    project_path=project["path_with_namespace"],
                ),
            ),
        }
        for project in projects
    ]

    _current_topic_url = url_for(
        _request,
        "stac_topic",
        path=dict(
            gitlab_base_uri=_gitlab_base_uri,
            token=_token,
            topic_name=topic["name"],
        ),
    )
    if pagination["prev_page"]:
        links.append(
            {
                "rel": "prev",
                "href": url_add_query_params(
                    _current_topic_url, {"page": pagination["prev_page"]}
                ),
            }
        )
    if pagination["next_page"]:
        links.append(
            {
                "rel": "next",
                "href": url_add_query_params(
                    _current_topic_url, {"page": pagination["next_page"]}
                ),
            }
        )

    if preview:
        links.append(
            {
                "rel": "preview",
                "href": preview,
            }
        )

    _gitlab_base_uri_slug = slugify(_gitlab_base_uri).replace("-", "")
    stac_id = f"{_gitlab_base_uri_slug}-{slugify(topic['name'])}-catalog"
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": stac_id,
        "title": title,
        "description": description,
        "links": [
            {
                "rel": "root",
                "href": url_for(
                    _request,
                    "stac_root",
                    path=dict(
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                    ),
                ),
            },
            {
                "rel": "self",
                "href": str(_request.url),
            },
            {
                "rel": "parent",
                "href": url_for(
                    _request,
                    "stac_root",
                    path=dict(
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                    ),
                ),
            },
            *links,
        ],
    }


def build_stac_for_project(
    topic: Topic,
    project: GitlabProject,
    readme: str,
    files: list[GitlabProjectFile],
    assets_rules: list[str],
    release: GitlabProjectRelease | None,
    release_source_format: str,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_base_uri_slug = slugify(_gitlab_base_uri).replace("-", "")

    readme_doc, readme_metadata = md.parse(readme)
    assets_mapping = _get_assets_mapping(assets_rules, readme_metadata)

    # STAC data

    stac_id = f"{_gitlab_base_uri_slug}-{slugify(topic['name'])}-{project['id']}"
    title = project["name_with_namespace"]
    description = md.remove_images(md.increase_headings(readme_doc, 2))
    keywords = _get_keywords(topic, project, readme_metadata)
    preview, preview_media_type = _get_preview(project, readme_metadata, readme_doc)
    license, license_url = _get_license(project, readme_metadata)
    producer, producer_url = _get_producer(project, readme_metadata, **context)
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

    # STAC generation

    stac_type = topic.get("default_type")
    stac_type = readme_metadata.get("type", stac_type)
    stac_type = stac_type if stac_type in ["item", "collection"] else "item"
    stac_extensions = [
        "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
    ]

    fields = {}
    assets = {}
    links = [
        {
            "rel": "root",
            "href": url_for(
                _request,
                "stac_root",
                path=dict(
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                ),
            ),
        },
        {
            "rel": "self",
            "href": str(_request.url),
        },
        {
            "rel": "parent",
            "href": url_for(
                _request,
                "stac_topic",
                path=dict(
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic_name=topic["name"],
                ),
            ),
        },
        {
            "rel": "bug_tracker",
            "title": "Issues",
            "href": project_issues_url(_gitlab_base_uri, project),
        },
        *(
            {
                "rel": "derived_from" if "stac" in _labels else "extras",
                "href": _href,
                "title": _title,
            }
            for _title, _href, _labels in resources_links
        ),
    ]
    providers = [
        {
            "name": f"GitLab ({_gitlab_base_uri})",
            "roles": ["host"],
            "url": project_url(_gitlab_base_uri, project),
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
                gitlab_base_uri=_gitlab_base_uri,
                token=_token,
                project_id=project["id"],
                ref=project["default_branch"],
                file_path=preview,
            ),
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
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    project_id=project["id"],
                    ref=project["default_branch"],
                    file_path=file_path,
                ),
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
                gitlab_base_uri=_gitlab_base_uri,
                token=_token,
                project_id=project["id"],
                ref=release["tag_name"],
                format=release_source_format,
            ),
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

    match stac_type:
        case "item":
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
                    **fields,
                },
                "links": links,
                "assets": assets,
                "collection": None,
            }
        case "collection":
            return {
                "stac_version": "1.0.0",
                "stac_extensions": stac_extensions,
                "type": "Collection",
                "id": stac_id,
                "title": title,
                "description": description,
                "keywords": keywords,
                "license": license,
                "providers": providers,
                "extent": {
                    "spatial": {"bbox": [spatial_extent]},
                    "temporal": {"interval": [temporal_extent]},
                },
                "links": links,
                "assets": assets,
                **fields,
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


def _get_keywords(topic: Topic, project: GitlabProject, metadata: dict) -> list[str]:
    topic_keyword = slugify(topic["name"])
    namespaces_keywords = [
        slugify(g) for g in project["path_with_namespace"].split("/")[:-1]
    ]
    readme_keywords = metadata.get("keywords", [])
    return list(dict.fromkeys([topic_keyword, *namespaces_keywords, *readme_keywords]))


def _get_preview(
    project: GitlabProject,
    metadata: dict,
    md_content: str,
) -> tuple[str | None, str | None]:
    preview = project["avatar_url"]
    preview = metadata.get("preview", preview)
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


def _get_producer(
    project: GitlabProject, metadata: dict, **context: STACContext
) -> tuple[str, str]:
    _gitlab_base_uri = context["gitlab_base_uri"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    producer = project["name_with_namespace"].split("/")[0].rstrip()
    producer = metadata.get("producer", producer)
    _producer_path = project["path_with_namespace"].split("/")[0]
    producer_url = f"{_gitlab_url}/{_producer_path}"
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
                    media_type = None
                    media_type, _ = mimetypes.guess_type(fpath)
                if media_type or not assets.get(file["path"]):
                    assets[file["path"]] = media_type
    return assets


def _get_resources_links(
    metadata: dict, **context: STACContext
) -> list[tuple[str, str]]:
    _metadata_resources = metadata.get("resources", {})
    return _retrieve_resources_links(_metadata_resources, **context)


def _retrieve_resources_links(
    mapping: dict, labels: list | None = None, **context: STACContext
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
    raw_link: str, key: str, labels: list, **context: STACContext
) -> tuple[str, str, list[str]]:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
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
                gitlab_base_uri=_gitlab_base_uri,
                token=_token,
                topic_name=key,
                project_path=path,
            ),
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
