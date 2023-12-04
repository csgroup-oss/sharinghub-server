from fastapi import Request
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient
from app.config import GITLAB_URL
from app.dependencies import GitlabTokenDep

router = APIRouter()


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
