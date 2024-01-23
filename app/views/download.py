import logging

from fastapi import Request
from fastapi.routing import APIRouter

from app.api.providers.gitlab import GitlabClient
from app.config import GITLAB_URL
from app.dependencies import GitlabTokenDep

logger = logging.getLogger("app")

router = APIRouter()


@router.get("/file/{project_path:path}/{ref}/{file_path:path}")
async def download_gitlab_file(
    request: Request,
    token: GitlabTokenDep,
    project_path: str,
    ref: str,
    file_path: str,
):
    """Download proxy for a GitLab project repository file."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.download_file(
        project_path=project_path,
        ref=ref,
        file_path=file_path,
    )


@router.get("/archive/{project_path:path}/{ref}/archive.{format}")
async def download_gitlab_archive(
    request: Request,
    token: GitlabTokenDep,
    project_path: str,
    ref: str,
    format: str,
):
    """Download proxy for a GitLab project archive."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.download_archive(
        project_path=project_path, ref=ref, format=format
    )
