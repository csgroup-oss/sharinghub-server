from fastapi import Request
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient
from app.dependencies import GitlabConfigDep, GitlabTokenDep

router = APIRouter()


@router.api_route(
    "/{endpoint:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def api_reverse_proxy(
    request: Request,
    endpoint: str,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
):
    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    return await gitlab_client.proxify(f"/{endpoint}", request)
