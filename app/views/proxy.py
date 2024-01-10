import json

from fastapi import Request
from fastapi.routing import APIRouter
from starlette.responses import JSONResponse

from app.api.gitlab import GitlabClient
from app.config import GITLAB_IGNORE_TOPICS, GITLAB_URL
from app.dependencies import GitlabTokenDep

router = APIRouter()


@router.get("/topics")
async def api_get_topics(
    token: GitlabTokenDep,
):
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    response = await gitlab_client.get_topics()
    results = [el for el in response if el.get("title", {}) not in GITLAB_IGNORE_TOPICS]
    return JSONResponse(content=results)


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
    return await gitlab_client.proxify(f"/{endpoint}", request)
