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

from fastapi import APIRouter, HTTPException, Response
from starlette.status import HTTP_400_BAD_REQUEST

from app.auth.depends import GitlabTokenDep
from app.providers.client.gitlab import GitlabClient
from app.settings import GITLAB_URL

router = APIRouter()


@router.get("/{project_path:path}")
async def check(
    project_path: str, token: GitlabTokenDep, info: bool = False
) -> Response:
    """Check wether a project is found or not, by id or path."""
    if project_path:
        gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
        if project_path.isdigit():
            project = await gitlab_client.get_project_from_id(id=int(project_path))
        else:
            project = await gitlab_client.get_project(path=project_path)
        if info:
            return Response(
                content=project.model_dump_json(
                    include={"id", "name", "path", "access_level"}
                ),
                media_type="application/json",
            )
        return Response()
    raise HTTPException(status_code=HTTP_400_BAD_REQUEST)
