from typing import TypeAlias, TypedDict

from fastapi import Request


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
