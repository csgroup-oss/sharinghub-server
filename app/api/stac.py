import mimetypes
from pathlib import Path
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
    project_archive_download_url,
    project_file_download_url,
    project_issues_url,
    project_url,
)
from app.utils import markdown as md
from app.utils.http import is_local, slugify

MEDIA_TYPES = {
    "geotiff": "image/tiff; application=geotiff",
    "cog": "image/tiff; application=geotiff; profile=cloud-optimized",
    "geojson": "application/geo+json",
}


class STACContext(TypedDict):
    request: Request
    gitlab_base_uri: str
    token: str


class TopicFields(TypedDict):
    title: str
    description: NotRequired[str]
    default_type: NotRequired[str]


class Topic(TopicFields):
    name: str


TopicSpec: TypeAlias = dict[str, TopicFields]


def build_stac_root(
    config: dict, topics: TopicSpec, **context: Unpack[STACContext]
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    title = config.get("title", "GitLab STAC Catalog")
    description = config.get(
        "description",
        f"Catalog generated from your [Gitlab]({_gitlab_url}) repositories with STAC Dataset Proxy.",
    )

    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                _request.url_for(
                    "stac_topic",
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic=topic,
                )
            ),
        }
        for topic in topics
    ]

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
                "href": str(_request.url),
            },
            {
                "rel": "self",
                "href": str(_request.url),
            },
            *topics_catalogs,
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
        f"{title} catalog generated from your [Gitlab]({_gitlab_url}) repositories with STAC Dataset Proxy.",
    )

    links = [
        {
            "rel": "child",
            "href": str(
                _request.url_for(
                    "stac_project",
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic=topic["name"],
                    project_path=project["path_with_namespace"],
                )
            ),
        }
        for project in projects
    ]

    _current_topic_url = _request.url_for(
        "stac_topic",
        gitlab_base_uri=_gitlab_base_uri,
        token=_token,
        topic=topic["name"],
    )
    if pagination["prev_page"]:
        links.append(
            {
                "rel": "prev",
                "href": str(
                    _current_topic_url.include_query_params(
                        page=pagination["prev_page"]
                    )
                ),
            }
        )
    if pagination["next_page"]:
        links.append(
            {
                "rel": "next",
                "href": str(
                    _current_topic_url.include_query_params(
                        page=pagination["next_page"]
                    )
                ),
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
                "href": str(
                    _request.url_for(
                        "stac_root",
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                    )
                ),
            },
            {
                "rel": "self",
                "href": str(_request.url),
            },
            {
                "rel": "parent",
                "href": str(
                    _request.url_for(
                        "stac_root",
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                    )
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

    readme_doc, readme_xml, readme_metadata = md.parse(readme)
    assets_mapping = _get_assets_mapping(assets_rules, readme_metadata)

    # STAC data

    stac_id = f"{_gitlab_base_uri_slug}-{slugify(topic['name'])}-{project['id']}"
    title = project["name_with_namespace"]
    description = md.remove_images(md.increase_headings(readme_doc, 2))
    keywords = _get_keywords(topic, project, readme_metadata)
    preview, preview_media_type = _get_preview(project, readme_metadata, readme_xml)
    license, license_url = _get_license(project, readme_metadata)
    producer, producer_url = _get_producer(project, readme_metadata, **context)
    spatial_extent, temporal_extent = _get_extent(project, readme_metadata)
    files_assets = _get_files_assets(files, assets_mapping)
    stac_links, extra_links = _get_resources_links(readme_metadata)

    ## Extensions

    ### Scientific Citation extension (https://github.com/stac-extensions/scientific)
    doi, doi_publications = _get_scientific_citations(readme_metadata, readme_xml)
    doi_link, doi_citation = doi

    # STAC generation

    stac_type = topic.get("default_type")
    stac_type = readme_metadata.get("type", stac_type)
    stac_type = stac_type if stac_type in ["item", "collection"] else "collection"
    stac_extensions = [
        "https://stac-extensions.github.io/scientific/v1.0.0/schema.json",
    ]

    if is_local(preview):
        preview = project_file_download_url(
            gitlab_base_uri=_gitlab_base_uri,
            token=_token,
            project=project,
            file_path=preview,
        )

    match stac_type:
        case "item":
            return {}
        case "collection":
            fields = {}
            links = []
            assets = {}

            if license_url:
                links.append(
                    {
                        "rel": "license",
                        "href": license_url,
                    }
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

            for file_path, file_media_type in files_assets:
                asset_id = f"file://{file_path}"
                assets[asset_id] = {
                    "href": project_file_download_url(
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                        project=project,
                        file_path=file_path,
                    ),
                    "title": file_path,
                    "roles": ["data"],
                }
                if file_media_type:
                    assets[asset_id]["type"] = file_media_type

            if release:
                archive_url = project_archive_download_url(
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    project=project,
                    ref=release["tag_name"],
                    format=release_source_format,
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
                extra_links.append(
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

            return {
                "stac_version": "1.0.0",
                "stac_extensions": stac_extensions,
                "type": "Collection",
                "id": stac_id,
                "title": title,
                "description": description,
                "keywords": keywords,
                "license": license,
                "providers": [
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
                ],
                "extent": {
                    "spatial": {"bbox": spatial_extent},
                    "temporal": {"interval": temporal_extent},
                },
                "links": [
                    {
                        "rel": "root",
                        "href": str(
                            _request.url_for(
                                "stac_root",
                                gitlab_base_uri=_gitlab_base_uri,
                                token=_token,
                            )
                        ),
                    },
                    {
                        "rel": "self",
                        "href": str(_request.url),
                    },
                    {
                        "rel": "parent",
                        "href": str(
                            _request.url_for(
                                "stac_topic",
                                gitlab_base_uri=_gitlab_base_uri,
                                token=_token,
                                topic=topic["name"],
                            )
                        ),
                    },
                    {
                        "rel": "bug_tracker",
                        "title": "Issues",
                        "href": project_issues_url(_gitlab_base_uri, project),
                    },
                    *(
                        {"rel": "extras", "href": _href, "title": _title}
                        for _title, _href in extra_links
                    ),
                    *(
                        {
                            "rel": "derived_from",
                            "href": str(
                                _request.url_for(
                                    "stac_project",
                                    gitlab_base_uri=_gitlab_base_uri,
                                    token=_token,
                                    topic=_topic,
                                    project_path=_path,
                                )
                            ),
                            "title": _title,
                        }
                        for _title, _topic, _path in stac_links
                    ),
                    *links,
                ],
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
    readme_xml: md.XMLElement,
) -> tuple[str | None, str | None]:
    preview = project["avatar_url"]
    preview = metadata.get("preview", preview)
    preview = metadata.get("thumbnail", preview)
    for img in readme_xml.xpath("//img"):
        if img.get("alt").lower().strip() in ["preview", "thumbnail"]:
            preview = img.get("src")
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
) -> tuple[list[list[float]], list[list[str | None]]]:
    extent = metadata.get("extent", {})
    spatial_extent = extent.get("bbox", [[-180.0, -90.0, 180.0, 90.0]])
    temporal_extent = extent.get(
        "temporal", [[project["created_at"], project["last_activity_at"]]]
    )
    return spatial_extent, temporal_extent


def _get_files_assets(
    files: list[GitlabProjectFile], assets_mapping: dict[str, str | None]
) -> list[tuple[str, str | None]]:
    assets = []
    for file in files:
        fpath = Path(file["path"])
        for glob in assets_mapping:
            if fpath.match(glob):
                if assets_mapping[glob]:
                    media_type = assets_mapping[glob]
                else:
                    media_type = None
                    media_type, _ = mimetypes.guess_type(fpath)
                assets.append((file["path"], media_type))
    return assets


def _get_resources_links(
    metadata: dict,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    stac_links = []
    extra_links = []

    _metadata_resources = metadata.get("resources", {})
    _metadata_stac_resources = _metadata_resources.get("stac", {})

    for _topic, val in _metadata_stac_resources.items():
        links = val if isinstance(val, list) else [val] if isinstance(val, str) else []
        for link in links:
            path = parse.urlparse(link).path.removeprefix("/")
            title = f"{_topic}: {path}"
            stac_links.append((title, _topic, path))

    for title, href in _metadata_resources.items():
        if title not in ["stac"]:
            extra_links.append((title, href))

    return stac_links, extra_links


def _get_scientific_citations(
    metadata: dict, readme_xml: md.XMLElement
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
    elif doi_match := readme_xml.xpath('//a[starts-with(@href, "https://doi.org")]'):
        for link in doi_match:
            href = link.get("href")
            text = "".join(link.itertext()).strip()
            if text.startswith(DOI_PREFIX):
                doi_link = href
                doi_citation = text.removeprefix(DOI_PREFIX).lstrip()
            else:
                doi_publications.append((href, text))

    if "publications" in metadata:
        for _doi_publication in metadata["publications"]:
            doi_publications.append(
                (_doi_publication.get("link"), _doi_publication.get("citation"))
            )

    return (doi_link, doi_citation), doi_publications
