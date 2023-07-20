from typing import NotRequired, TypeAlias, TypedDict, Unpack

from fastapi import Request

from app.api.gitlab import GitlabProjectInfo
from app.utils.http import is_local, slugify
from app.utils.markdown import make_description_from_readme, parse_markdown


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

    description = (
        f"Catalog generated from your [Gitlab]({_gitlab_base_uri}) repositories with STAC Dataset Proxy.",
    )

    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                _request.url_for("topic_catalog", token=_token, topic_name=topic_name)
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
    projects: list[GitlabProjectInfo],
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]

    title = fields["title"]
    description = fields.get(
        "description",
        f"{title} catalog generated from your [Gitlab]({_gitlab_base_uri}) repositories with STAC Dataset Proxy.",
    )

    links = [
        {
            "rel": "child",
            "href": str(
                _request.url_for(
                    "collection",
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
                "href": str(_request.url_for("root_catalog", token=_token)),
            },
            {
                "rel": "self",
                "href": str(_request.url),
            },
            {
                "rel": "parent",
                "href": str(_request.url_for("root_catalog", token=_token)),
            },
            *links,
        ],
    }


def build_collection(
    topic_name: str,
    project_path: str,
    project: GitlabProjectInfo,
    readme: str,
    **context: Unpack[STACContext],
) -> dict:
    _request = context["request"]
    _gitlab_base_uri = context["gitlab_base_uri"]
    _token = context["token"]

    links = []

    readme_doc, readme_xml, readme_metadata = parse_markdown(readme)

    description = make_description_from_readme(readme_doc)
    extent = readme_metadata.get("extent", {})
    spatial_bbox = extent.get("bbox", [[-180, -90, 180, 90]])
    temporal_interval = extent.get(
        "temporal", [[project["created_at"], project["last_activity_at"]]]
    )

    if "license" in readme_metadata:
        license = readme_metadata["license"]
        license_url = readme_metadata.get("license_url")
    elif project["license_url"]:
        license = project["license"]["key"]
        license_url = project["license_url"]
    else:
        license = "proprietary"
        license_url = None

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
    if is_local(preview):
        preview = f"{_gitlab_base_uri}/{project_path}/raw/{project['default_branch']}/{preview}"
    if preview:
        links.append(
            {
                "rel": "preview",
                "href": preview,
            }
        )

    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
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
                "url": _gitlab_base_uri,
            }
        ],
        "extent": {
            "spatial": {"bbox": spatial_bbox},
            "temporal": {"interval": temporal_interval},
        },
        "links": [
            {
                "rel": "root",
                "href": str(_request.url_for("root_catalog", token=_token)),
            },
            {
                "rel": "self",
                "href": str(_request.url),
            },
            {
                "rel": "parent",
                "href": str(
                    _request.url_for(
                        "topic_catalog", token=_token, topic_name=topic_name
                    )
                ),
            },
            {
                "rel": "license",
                "href": license_url,
            },
            *links,
        ],
    }
