from fastapi import Request
from fastapi.routing import APIRouter

from app.auth import GitlabTokenDep
from app.providers.client import GitlabClient
from app.settings import GITLAB_IGNORE_TOPICS, GITLAB_URL, TAGS_OPTIONS
from app.stac.api.category import get_categories

router = APIRouter()

_IGNORE_LIST = [*GITLAB_IGNORE_TOPICS, *(c.gitlab_topic for c in get_categories())]


@router.get("/tags")
async def api_get_tags(
    token: GitlabTokenDep,
):
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    topics_from_gitlab = await gitlab_client.get_topics()
    topics_from_gitlab = [
        t
        for t in topics_from_gitlab
        if t.name not in _IGNORE_LIST
        and t.total_projects_count
        >= TAGS_OPTIONS.get("gitlab", {}).get("minimum_count", 0)
    ]
    results = {
        "topics_from_gitlab": [t.name for t in topics_from_gitlab],
        **TAGS_OPTIONS,
    }
    return results


@router.api_route(
    "/{endpoint:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def api_reverse_proxy(
    request: Request,
    endpoint: str,
    token: GitlabTokenDep,
):
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.rest_proxy(f"/{endpoint}", request)