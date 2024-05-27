# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from fastapi import Request
from fastapi.responses import StreamingResponse
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
) -> StreamingResponse:
    """Download proxy for a GitLab project repository file."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.download_file(
        project_path=project_path,
        ref=ref,
        file_path=file_path,
        file_cache=cache,
        request=request,
    )


@router.get("/{project_path:path}/archive.{archive_format}")
async def download_gitlab_archive(
    request: Request,
    token: GitlabTokenDep,
    project_path: str,
    ref: str,
    archive_format: str,
) -> StreamingResponse:
    """Download proxy for a GitLab project archive."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    return await gitlab_client.download_archive(
        project_path=project_path,
        ref=ref,
        archive_format=archive_format,
        request=request,
    )
