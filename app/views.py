from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from .config import GITLAB_API_URL, GITLAB_TOPICS, GITLAB_URL
from .gitlab import get_project_metadata, get_projects, get_topic
from .utils import slugify

router = APIRouter(prefix="/{token}", tags=["stac"])


@router.get("/")
async def index(request: Request, token: str):
    return RedirectResponse(request.url_for("root_catalog", token=token))


@router.get("/catalog.json")
async def root_catalog(request: Request, token: str):
    topics_catalogs = [
        {
            "rel": "child",
            "href": str(
                request.url_for("topic_catalog", token=token, topic_name=topic)
            ),
        }
        for topic in GITLAB_TOPICS
    ]
    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": "gitlab-stac-catalog",
        "title": "GitLab STAC Catalog",
        "description": f"Catalog generated from your [Gitlab]({GITLAB_URL}) repositories with STAC Dataset Proxy.",
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


@router.get("/{topic_name:str}/catalog.json")
async def topic_catalog(request: Request, token: str, topic_name: str):
    topic = await get_topic(GITLAB_API_URL, token, topic_name)

    links = []
    if topic["id"]:
        projects = await get_projects(GITLAB_API_URL, token, topic_name)
        for project in projects:
            links.append(
                {
                    "rel": "child",
                    "href": str(
                        request.url_for(
                            "collection",
                            token=token,
                            topic_name=topic_name,
                            project_path=project["path_with_namespace"],
                        )
                    ),
                }
            )

    return {
        "stac_version": "1.0.0",
        "type": "Catalog",
        "id": f"gitlab-{slugify(topic['name'])}-stac-catalog",
        "title": topic["title"],
        "description": topic["description"]
        if topic["description"]
        else f"{topic['title']} catalog generated from your [Gitlab]({GITLAB_URL}) repositories with STAC Dataset Proxy.",
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


@router.get("/{topic_name:str}/{project_path:path}/collection.json")
async def collection(request: Request, token: str, topic_name: str, project_path: str):
    project, metadata = await get_project_metadata(GITLAB_API_URL, token, project_path)
    collection = {
        "stac_version": "1.0.0",
        "stac_extensions": ["collection-assets"],
        "type": "Collection",
        "id": f"gitlab-{slugify(project['name_with_namespace'])}",
        "title": project["name_with_namespace"],
        "description": project["description"]
        if project["description"]
        else f"{project['name']} collection generated from [Gitlab]({project['web_url']}) repository with STAC Dataset Proxy.",
    }
    collection |= metadata
    if "links" in collection:
        collection["links"].extend(
            [
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
                    "href": str(
                        request.url_for(
                            "topic_catalog", token=token, topic_name=topic_name
                        )
                    ),
                },
            ]
        )
    return collection
