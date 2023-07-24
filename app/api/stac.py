import mimetypes
import re
from pathlib import Path
from typing import NotRequired, TypeAlias, TypedDict, Unpack

from fastapi import Request

from app.api.gitlab import (
    GitlabMemberRole,
    GitlabProject,
    GitlabProjectFile,
    GitlabProjectMember,
    GitlabProjectRelease,
    gitlab_url,
    project_file_download_url,
    project_url,
)
from app.config import ASSETS_FILE_EXTENSIONS, RELEASE_SOURCE_ASSET_FORMAT
from app.utils import markdown as md
from app.utils.http import is_local, slugify


class STACContext(TypedDict):
    request: Request
    gitlab_base_uri: str
    token: str


class TopicFields(TypedDict):
    title: str
    description: NotRequired[str]


TopicSpec: TypeAlias = dict[str, TopicFields]


def build_root_catalog(topics: TopicSpec, **context: Unpack[STACContext]) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    description = (
        f"Catalog generated from your [Gitlab]({_gitlab_url}) repositories with STAC Dataset Proxy.",
    )

    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                _request.url_for(
                    "topic_catalog",
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic_name=topic_name,
                )
            ),
        }
        for topic_name in topics
    ]
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": "gitlab-stac-catalog",
        "title": "GitLab STAC Catalog",
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


def build_topic_catalog(
    name: str,
    fields: TopicFields,
    projects: list[GitlabProject],
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]
    _gitlab_url = gitlab_url(_gitlab_base_uri)

    title = fields["title"]
    description = fields.get(
        "description",
        f"{title} catalog generated from your [Gitlab]({_gitlab_url}) repositories with STAC Dataset Proxy.",
    )

    links = [
        {
            "rel": "child",
            "href": str(
                _request.url_for(
                    "project_collection",
                    gitlab_base_uri=_gitlab_base_uri,
                    token=_token,
                    topic_name=name,
                    project_path=project["path_with_namespace"],
                )
            ),
        }
        for project in projects
    ]
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": f"gitlab-{slugify(name)}-stac-catalog",
        "title": title,
        "description": description,
        "links": [
            {
                "rel": "root",
                "href": str(
                    _request.url_for(
                        "root_catalog",
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
                        "root_catalog",
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                    )
                ),
            },
            *links,
        ],
    }


def build_collection(
    topic_name: str,
    project: GitlabProject,
    readme: str,
    members: list[GitlabProjectMember],
    files: list[GitlabProjectFile],
    release: GitlabProjectRelease | None,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]

    extensions = []
    assets = {}
    extra_fields = {}
    extra_links = []
    extra_providers = []

    readme_doc, readme_xml, readme_metadata = md.parse(readme)

    # STAC Collection fields

    description = md.remove_images(md.increase_headings(readme_doc, 2))

    extent = readme_metadata.get("extent", {})
    spatial_bbox = extent.get("bbox", [[-180, -90, 180, 90]])
    temporal_interval = extent.get(
        "temporal", [[project["created_at"], project["last_activity_at"]]]
    )

    if "license" in readme_metadata:
        # Must be SPDX identifier: https://spdx.org/licenses/
        license = readme_metadata["license"]
        license_url = None
    elif project["license_url"]:
        license = "proprietary"
        license_url = project["license_url"]
    else:
        # Private collection
        license = None
        license_url = None

    if license:
        extra_links.append(
            {
                "rel": "license",
                "href": license_url,
            }
        )

    keywords = readme_metadata.get("keywords", [])
    topic_keyword = slugify(topic_name)
    if topic_keyword not in keywords:
        keywords.append(topic_keyword)

    preview = project["avatar_url"]
    preview = readme_metadata.get("preview", preview)
    preview = readme_metadata.get("thumbnail", preview)
    for img in readme_xml.xpath("//img"):
        if img.get("alt").lower().strip() in ["preview", "thumbnail"]:
            preview = img.get("src")
    media_type, _ = mimetypes.guess_type(preview) if preview else (None, None)
    if is_local(preview):
        preview = project_file_download_url(
            gitlab_base_uri=_gitlab_base_uri,
            project=project,
            file_path=preview,
            token=_token,
        )
    if preview:
        assets["preview"] = {
            "href": preview,
            "title": "Preview",
            "roles": ["thumbnail"],
        }
        if media_type:
            assets["preview"]["type"] = media_type
        extra_links.append(
            {
                "rel": "preview",
                "href": preview,
            }
        )

    assets_globs = readme_metadata.get("assets", [])
    for file in files:
        fpath = Path(file["path"])
        match_ext = any(file["name"].endswith(ext) for ext in ASSETS_FILE_EXTENSIONS)
        match_globs = any(fpath.match(glob) for glob in assets_globs)
        if match_ext or match_globs:
            media_type, _ = mimetypes.guess_type(file["name"])
            assets[file["id"]] = {
                "href": project_file_download_url(
                    gitlab_base_uri=_gitlab_base_uri,
                    project=project,
                    file_path=file["path"],
                    token=_token,
                ),
                "title": file["path"],
                "roles": ["data"],
            }
            if media_type:
                assets[file["id"]]["type"] = media_type

    if release:
        for source in release["assets"]["sources"]:
            if source["format"] == RELEASE_SOURCE_ASSET_FORMAT:
                media_type, _ = mimetypes.guess_type(source["url"])
                assets[release["tag_name"]] = {
                    "href": source["url"],
                    "title": f"Release {release['tag_name']}",
                    "description": release["name"],
                    "roles": ["data"],
                }
                if release["description"]:
                    assets[release["tag_name"]][
                        "description"
                    ] += f":\n\n{release['description']}"
                if media_type:
                    assets[release["tag_name"]]["type"] = media_type

    owners = [m for m in members if m["access_level"] == GitlabMemberRole.owner]
    maintainers = [
        m for m in members if m["access_level"] == GitlabMemberRole.maintainer
    ]
    developers = [m for m in members if m["access_level"] == GitlabMemberRole.developer]
    producers = (
        owners
        if owners
        else maintainers
        if maintainers
        else developers
        if developers
        else []
    )
    extra_providers.extend(
        [
            {
                "name": f"{member['name']} ({member['username']})",
                "roles": ["producer"],
                "url": member["web_url"],
            }
            for member in producers
        ]
    )

    # Scientific Citation extension (https://github.com/stac-extensions/scientific)

    if "doi" in readme_metadata:
        doi_name = readme_metadata["doi"].get("name")
        doi_link = readme_metadata["doi"].get("link", f"https://doi.org/{doi_name}")
        doi_citation = readme_metadata["doi"].get("citation")
    elif match := re.search(
        r"^DOI\s(?P<doi>.*):\s(?P<citation>.*)", readme_doc, re.MULTILINE
    ):
        capture = match.groupdict()
        doi_name = capture["doi"]
        doi_link = f"https://doi.org/{doi_name}"
        doi_citation = capture["citation"]
    else:
        doi_name = doi_link = doi_citation = None

    if "publications" in readme_metadata:
        doi_publications = readme_metadata["doi"].get("publications")
    elif match := re.search(r"^Publications(\w)?:", readme_doc, re.MULTILINE):
        doi_publications = []
        if e := readme_xml.xpath('.//p[starts-with(text(),"Publications")]'):
            pub = e[0]
            pub_next = pub.getnext()
            if pub_next.tag == "ul":
                for li in pub_next:
                    content = "".join(li.itertext())
                    doi, citation = content.split(":", 1)
                    doi_publications.append(
                        {
                            "doi": doi.strip(),
                            "citation": citation.strip(),
                        }
                    )
    else:
        doi_publications = None

    if doi_name:
        extensions.append(
            "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
        )
        extra_fields["sci:doi"] = doi_name
        extra_links.append(
            {
                "rel": "cite-as",
                "href": doi_link,
            }
        )
        if doi_citation:
            extra_fields["sci:citation"] = doi_citation
        if doi_publications:
            extra_fields["sci:publications"] = doi_publications

    return {
        "stac_version": "1.0.0",
        "stac_extensions": extensions,
        "type": "Collection",
        "id": f"gitlab-{slugify(project['name_with_namespace'])}",
        "title": project["name_with_namespace"],
        "description": description,
        "keywords": keywords,
        "license": license,
        "providers": [
            {
                "name": "GitLab",
                "roles": ["host"],
                "url": project_url(_gitlab_base_uri, project["path_with_namespace"]),
            },
            *extra_providers,
        ],
        "extent": {
            "spatial": {"bbox": spatial_bbox},
            "temporal": {"interval": temporal_interval},
        },
        "links": [
            {
                "rel": "root",
                "href": str(
                    _request.url_for(
                        "root_catalog",
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
                        "topic_catalog",
                        gitlab_base_uri=_gitlab_base_uri,
                        token=_token,
                        topic_name=topic_name,
                    )
                ),
            },
            *extra_links,
        ],
        "assets": assets,
        **extra_fields,
    }
