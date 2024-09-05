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

import json

from fastapi import APIRouter, HTTPException, Response
from starlette.status import HTTP_400_BAD_REQUEST

from app.auth.depends import GitlabTokenDep
from app.providers.client.gitlab import GitlabClient
from app.settings import CHECKER_CACHE_TIMEOUT, GITLAB_URL
from app.utils.cache import cache

router = APIRouter()


@router.get("/{project_id_or_path:path}")
async def check(
    project_id_or_path: str, token: GitlabTokenDep, info: bool = False
) -> Response:
    """Check wether a project is found or not, by id or path."""
    if not project_id_or_path:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST)

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)

    user: str | None = await cache.get(token.value, namespace="user")
    if not user:
        user = await gitlab_client.get_user()
        await cache.set(token.value, user, namespace="user")

    if project_id_or_path.isdigit():
        project_id = int(project_id_or_path)
        project_path: str | None = await cache.get(project_id, namespace="project-path")
        if not project_path:
            project_path = await gitlab_client.get_project_path(id=project_id)
            await cache.set(
                project_id,
                project_path,
                ttl=int(CHECKER_CACHE_TIMEOUT),
                namespace="project-path",
            )
    else:
        project_path = project_id_or_path

    projectinfo: dict | None = await cache.get(
        (user, project_path), namespace="project-info"
    )
    if not projectinfo:
        project = await gitlab_client.get_project(path=project_path)
        projectinfo = project.model_dump(
            mode="json", include={"id", "name", "path", "access_level", "categories"}
        )
        projectinfo["categories"] = [c["id"] for c in projectinfo["categories"]]
        await cache.set(
            (user, project_path),
            projectinfo,
            ttl=int(CHECKER_CACHE_TIMEOUT),
            namespace="project-info",
        )

    if info:
        return Response(
            content=json.dumps(projectinfo),
            media_type="application/json",
        )
    return Response()
