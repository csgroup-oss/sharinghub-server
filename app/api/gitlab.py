import enum
from typing import Any, TypedDict

import aiohttp
from fastapi import HTTPException

from app.utils.http import AiohttpClient, url_add_query_params, urlsafe_path


class GitlabMemberRole(enum.IntEnum):
    """From https://docs.gitlab.com/ee/api/members.html#roles"""

    no_access = 0
    minimal_access = 5
    guest = 10
    reporter = 20
    developer = 30
    maintainer = 40
    owner = 50


class GitlabProject(TypedDict):
    id: str
    description: str | None
    name: str
    name_with_namespace: str
    path: str
    path_with_namespace: str
    web_url: str
    created_at: str
    last_activity_at: str
    license_url: str | None
    license: dict[str]
    default_branch: str | None
    avatar_url: str | None
    topics: list[str]


class GitlabProjectFile(TypedDict):
    id: str
    name: str
    path: str


class GitlabProjectMember(TypedDict):
    id: str
    username: str
    name: str
    web_url: str
    access_level: int


def gitlab_url(gitlab_base_uri: str) -> str:
    return f"https://{gitlab_base_uri.removesuffix('/')}"


def gitlab_api_url(gitlab_base_uri: str) -> str:
    return f"{gitlab_url(gitlab_base_uri)}/api/v4"


def project_url(gitlab_base_uri: str, project_path: str) -> str:
    return f"{gitlab_url(gitlab_base_uri)}/{project_path}"


def project_api_url(project_path: str, gitlab_api_url: str = "") -> str:
    return f"{gitlab_api_url}/projects/{urlsafe_path(project_path)}"


def project_api_file_raw_url(
    gitlab_base_uri: str, project: GitlabProject, file_path: str, token: str
) -> str:
    _project_api_url = project_api_url(
        project["path_with_namespace"],
        gitlab_api_url(gitlab_base_uri),
    )
    return f"{_project_api_url}/repository/files/{urlsafe_path(file_path)}/raw?ref={project['default_branch']}&lfs=true&private_token={token}"


class GitlabClient:
    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url
        self.token = token

    async def get_projects(self, topic_name: str) -> list[GitlabProject]:
        return await self._request_iterate(f"/projects?topic={topic_name}&simple=true")

    async def get_project(self, project_path: str) -> GitlabProject:
        return await self._request(f"{project_api_url(project_path)}?license=true")

    async def get_readme(self, project: GitlabProject) -> str:
        _project_path = project["path_with_namespace"]
        try:
            readme = await self._request(
                f"{project_api_url(_project_path)}/repository/files/README.md/raw",
                media_type="text",
            )
            return readme.strip()
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                raise HTTPException(
                    status_code=418, detail="Missing READMD.md, unprocessable project"
                ) from http_exc
            raise http_exc

    async def get_members(self, project: GitlabProject) -> list[GitlabProjectMember]:
        _project_path = project["path_with_namespace"]
        return await self._request(f"{project_api_url(_project_path)}/members")

    async def get_files(self, project: GitlabProject) -> list[GitlabProjectFile]:
        _project_path = project["path_with_namespace"]
        return [
            file
            for file in await self._request_iterate(
                f"{project_api_url(_project_path)}/repository/tree?recursive=true"
            )
            if file["type"] == "blob"
        ]

    async def _request(
        self, endpoint: str, media_type="json"
    ) -> dict[str, Any] | list[Any] | str:
        async with AiohttpClient() as client:
            url = f"{self.api_url}{endpoint}"
            async with client.get(url, headers={"PRIVATE-TOKEN": self.token}) as resp:
                if resp.ok:
                    match media_type:
                        case "text":
                            return await resp.text()
                        case "json" | _:
                            return await resp.json()
                raise HTTPException(
                    status_code=resp.status,
                    detail=f"{resp.url}: {await resp.text()}",
                )

    async def _request_iterate(self, endpoint: str) -> list[Any]:
        items = []
        params = {
            "per_page": 100,
            "pagination": "keyset",
            "order_by": "id",
            "sort": "asc",
        }

        async with AiohttpClient() as client:
            url = f"{self.api_url}{endpoint}"
            url = url_add_query_params(url, params)

            while url:
                async with client.get(
                    url, headers={"PRIVATE-TOKEN": self.token}
                ) as resp:
                    if resp.ok:
                        content = await resp.json()
                        if not isinstance(content, list):
                            raise HTTPException(
                                status_code=422,
                                detail="Unexpected: requested API do not return a list",
                            )
                        items.extend(content)
                        url = self._get_next_link(resp)
                    else:
                        raise HTTPException(
                            status_code=resp.status,
                            detail=f"{resp.url}: {await resp.text()}",
                        )

            return items

    def _get_next_link(self, response: aiohttp.ClientResponse) -> str | None:
        if link_header := response.headers.get("Link"):
            links = link_header.split(",")
            for link_desc in links:
                link, rel, *_ = link_desc.strip().split(";")
                link = link.strip("<>")
                rel = rel.strip().removeprefix("rel=").strip('"')
                if rel == "next":
                    return link
        return None
