import logging

from fastapi import Request
from fastapi.routing import APIRouter

from app.auth import GitlabTokenDep
from app.providers.client import GitlabClient
from app.settings import GITLAB_URL

logger = logging.getLogger("app")

router = APIRouter()


@router.get("/{project_path:path}/repository/{file_path:path}")
async def download_gitlab_file(
    request: Request,
    token: GitlabTokenDep,
    project_path: str,
    file_path: str,
    ref: str,
    cache: int = 0,
):
    """Download proxy for a GitLab project repository file."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.download_file(
        project_path=project_path,
        ref=ref,
        file_path=file_path,
        file_cache=cache,
        request=request,
    )


@router.get("/{project_path:path}/archive.{format}")
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
        project_path=project_path, ref=ref, format=format, request=request
    )
