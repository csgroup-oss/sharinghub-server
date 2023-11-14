from fastapi import APIRouter, Request

from app.api.gitlab import GitlabClient
from app.dependencies import GitlabConfigDep, GitlabTokenDep

router = APIRouter()


@router.get("/{project_path:path}")
async def stac_resolve(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    project_path: str,
):
    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    project = await gitlab_client.get_project(project_path)
    return {"project_id": project["id"]}
