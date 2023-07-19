from typing import TypeAlias, TypedDict

from fastapi import Request

from app.api.gitlab import GitlabProjectInfo
from app.utils.http import slugify


class TopicFields(TypedDict):
    title: str
    description: str | None


TopicSpec: TypeAlias = dict[str, TopicFields]


def build_root_catalog(
    topics: TopicSpec, description: str, request: Request, token: str
) -> dict:
    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                request.url_for("topic_catalog", token=token, topic_name=topic_name)
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
                "href": str(request.url),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            *topics_catalogs,
        ],
    }


def build_topic_catalog(
    name: str,
    title: str,
    description: str,
    projects: list[GitlabProjectInfo],
    request: Request,
    token: str,
) -> dict:
    links = [
        {
            "rel": "child",
            "href": str(
                request.url_for(
                    "collection",
                    token=token,
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
                "href": str(request.url_for("root_catalog", token=token)),
            },
            {
                "rel": "self",
                "href": str(request.url),
            },
            {
                "rel": "parent",
                "href": str(request.url_for("root_catalog", token=token)),
            },
            *links,
        ],
    }
