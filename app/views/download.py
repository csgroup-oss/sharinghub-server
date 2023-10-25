import logging

from fastapi import Request
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabArchiveFormat, GitlabClient
from app.dependencies import GitlabConfigDep, GitlabTokenDep

logger = logging.getLogger("app")

router = APIRouter()


@router.get("/file/{project_id}/{ref}/{file_path:path}")
async def download_gitlab_file(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    project_id: int,
    ref: str,
    file_path: str,
):
    """Download proxy for a GitLab project repository file."""
    gitlab_client = GitlabClient(
        url=gitlab_config["url"], token=token.value, request=request
    )
    return await gitlab_client.download_file(
        project_id=project_id,
        ref=ref,
        file_path=file_path,
    )


@router.get("/archive/{project_id}/{ref}/archive.{format}")
async def download_gitlab_archive(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    project_id: int,
    ref: str,
    format: GitlabArchiveFormat,
):
    """Download proxy for a GitLab project archive."""
    gitlab_client = GitlabClient(
        url=gitlab_config["url"], token=token.value, request=request
    )
    return await gitlab_client.download_archive(
        project_id=project_id, ref=ref, format=format
    )
