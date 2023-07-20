import enum
from typing import Any, TypedDict
from urllib import parse

import aiohttp
from fastapi import HTTPException

from app.utils.http import AiohttpClient, urlsafe_path


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


class GitlabMember(TypedDict):
    id: str
    username: str
    name: str
    web_url: str
    access_level: int


def gitlab_url(gitlab_base_uri: str) -> str:
    return f"https://{gitlab_base_uri.removesuffix('/')}"


def gitlab_api_url(gitlab_base_uri: str) -> str:
    return f"{gitlab_url(gitlab_base_uri)}/api/v4"


def project_api_url(project_path: str, gitlab_api_url: str = "") -> str:
    return f"{gitlab_api_url}/projects/{urlsafe_path(project_path)}"


def project_api_file_raw_url(
    gitlab_url: str, project: GitlabProject, file_path: str, token: str
) -> str:
    _project_api_url = project_api_url(
        project["path_with_namespace"],
        gitlab_api_url(gitlab_url.removeprefix("https://")),
    )
    return f"{_project_api_url}/repository/files/{urlsafe_path(file_path)}/raw?ref={project['default_branch']}&private_token={token}"


class GitlabClient:
    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url
        self.token = token

    async def get_projects(self, topic_name: str) -> list[GitlabProject]:
        return await self._request(
            f"/projects?topic={topic_name}&simple=true", collect=True
        )

    async def get_project(self, project_path: str) -> GitlabProject:
        return await self._request(f"{project_api_url(project_path)}?license=true")

    async def get_readme(self, project_path: str) -> str:
        return (
            await self._request(
                f"{project_api_url(project_path)}/repository/files/README.md/raw",
                media_type="text",
            )
        ).strip()

    async def get_members(self, project_path: str) -> list[GitlabMember]:
        return await self._request(f"{project_api_url(project_path)}/members")

    async def _request(
        self, endpoint: str, media_type="json", collect: bool = False
    ) -> dict[str, Any] | list[Any] | str:
        async with AiohttpClient() as client:
            link = f"{self.api_url}{endpoint}"
            if collect:
                params = {
                    "per_page": 20,
                    "pagination": "keyset",
                    "order_by": "id",
                    "sort": "asc",
                }
                url_parts = list(parse.urlparse(link))
                url_parts[4] = parse.urlencode(
                    dict(parse.parse_qsl(url_parts[4])) | params
                )
                link = parse.urlunparse(url_parts)
            async with client.get(link, headers={"PRIVATE-TOKEN": self.token}) as resp:
                if resp.ok:
                    match media_type:
                        case "text":
                            return await resp.text()
                        case "json" | _:
                            if collect:
                                return await self._collect(client, resp)
                            return await resp.json()
                raise HTTPException(
                    status_code=resp.status,
                    detail=f"{resp.url}: {await resp.text()}",
                )

    async def _collect(
        self, client: aiohttp.ClientSession, response: aiohttp.ClientResponse
    ) -> list[Any]:
        items = await response.json()

        if not isinstance(items, list):
            raise HTTPException(
                status_code=422, detail="Unexpected: requested API do not return a list"
            )

        next_link = self._get_next_link(response)
        while next_link:
            async with client.get(
                next_link, headers={"PRIVATE-TOKEN": self.token}
            ) as resp:
                if resp.ok:
                    items.extend(await resp.json())
                    next_link = self._get_next_link(resp)
                else:
                    raise HTTPException(status_code=resp.status)
                next_link = None

        return items

    def _get_next_link(self, response: aiohttp.ClientResponse) -> str | None:
        if next_link_header := response.headers.get("Link"):
            next_link, rel, *_ = next_link_header.split(";")
            next_link = next_link.strip("<>")
            rel = rel.strip().removeprefix("rel=").strip('"')
            if rel == "next":
                return next_link
        return None
