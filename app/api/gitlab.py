import logging
from typing import Any, NotRequired, TypedDict

import aiohttp
from fastapi import HTTPException

from app.utils.http import AiohttpClient, url_add_query_params, urlsafe_path

logger = logging.getLogger("app")

GITLAB_LICENSES_SPDX_MAPPING = {
    "agpl-3.0": "AGPL-3.0",
    "apache-2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsl-1.0": "BSL-1.0",
    "cc0-1.0": "CC0-1.0",
    "epl-2.0": "EPL-2.0",
    "gpl-2.0": "GPL-2.0",
    "gpl-3.0": "GPL-3.0",
    "lgpl-2.1": "LGPL-2.1",
    "mit": "MIT",
    "mpl-2.0": "MPL-2.0",
    "unlicense": "Unlicense",
}


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
    license_url: NotRequired[str | None]
    license: NotRequired["_GitlabProjectLicense"]
    default_branch: str | None
    avatar_url: str | None
    topics: list[str]


class _GitlabProjectLicense(TypedDict):
    key: str
    name: str
    html_url: str


class GitlabProjectFile(TypedDict):
    id: str
    name: str
    path: str


class GitlabProjectRelease(TypedDict):
    name: str
    tag_name: str
    description: str
    commit_path: str
    tag_path: str
    assets: "_GitlabProjectReleaseAssets"


class _GitlabProjectReleaseAssets(TypedDict):
    count: int
    sources: list["_GitlabProjectReleaseSources"]


class _GitlabProjectReleaseSources(TypedDict):
    format: str
    url: str


def gitlab_url(gitlab_base_uri: str) -> str:
    return f"https://{gitlab_base_uri.removesuffix('/')}"


def project_url(gitlab_base_uri: str, project: GitlabProject) -> str:
    return f"{gitlab_url(gitlab_base_uri)}/{project['path_with_namespace']}"


def project_file_download_url(
    gitlab_base_uri: str, token: str, project: GitlabProject, file_path: str
) -> str:
    _project_api_url = _get_project_api_url(
        project["id"], _get_gitlab_api_url(gitlab_base_uri)
    )
    _fpath = urlsafe_path(file_path)
    _ref = project["default_branch"]
    return f"{_project_api_url}/repository/files/{_fpath}/raw?ref={_ref}&lfs=true&private_token={token}"


def project_archive_download_url(
    gitlab_base_uri: str, token: str, project: GitlabProject, ref: str, format: str
) -> str:
    _project_api_url = _get_project_api_url(
        project["id"], _get_gitlab_api_url(gitlab_base_uri)
    )
    return f"{_project_api_url}/repository/archive.{format}?sha={ref}&private_token={token}"


def _get_gitlab_api_url(gitlab_base_uri: str) -> str:
    return f"{gitlab_url(gitlab_base_uri)}/api/v4"


def _get_project_api_url(project_id: str | int, gitlab_api_url: str = "") -> str:
    _project_id = urlsafe_path(str(project_id))
    return f"{gitlab_api_url}/projects/{_project_id}"


class GitlabClient:
    def __init__(self, base_uri: str, token: str) -> None:
        self.base_uri = base_uri
        self.url = gitlab_url(base_uri)
        self.api_url = _get_gitlab_api_url(base_uri)
        self.token = token

    async def get_projects(self, topic_name: str) -> list[GitlabProject]:
        return await self._request_iterate(f"/projects?topic={topic_name}&simple=true")

    async def get_project(self, project_path: str) -> GitlabProject:
        return await self._request(f"{_get_project_api_url(project_path)}?license=true")

    async def get_readme(self, project: GitlabProject) -> str:
        try:
            readme = await self._request(
                f"{_get_project_api_url(project['id'])}/repository/files/README.md/raw",
                media_type="text",
            )
            return readme.strip()
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                raise HTTPException(
                    status_code=418, detail="Missing READMD.md, unprocessable project"
                ) from http_exc
            raise http_exc

    async def get_files(self, project: GitlabProject) -> list[GitlabProjectFile]:
        return [
            file
            for file in await self._request_iterate(
                f"{_get_project_api_url(project['id'])}/repository/tree?recursive=true"
            )
            if file["type"] == "blob"
        ]

    async def get_latest_release(
        self, project: GitlabProject
    ) -> GitlabProjectRelease | None:
        try:
            return await self._request(
                f"{_get_project_api_url(project['id'])}/releases/permalink/latest"
            )
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                return None
            raise http_exc

    async def _request(
        self, endpoint: str, media_type="json"
    ) -> dict[str, Any] | list[Any] | str:
        async with AiohttpClient() as client:
            url = f"{self.api_url}{endpoint}"
            logger.debug(f"Request {endpoint}")
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

    async def _request_iterate(self, endpoint: str, per_page=100) -> list[Any]:
        items = []
        params = {
            "per_page": per_page,
            "pagination": "keyset",
            "order_by": "id",
            "sort": "asc",
        }

        async with AiohttpClient() as client:
            url = f"{self.api_url}{endpoint}"
            url = url_add_query_params(url, params)

            logger.debug(f"Request iterate {endpoint}")
            while url:
                logger.debug(f"\t- {url}")
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
                        links = self._get_links_from_headers(resp)
                        url = links.get("next") if len(content) == per_page else None
                    else:
                        raise HTTPException(
                            status_code=resp.status,
                            detail=f"{resp.url}: {await resp.text()}",
                        )

            return items

    def _get_links_from_headers(self, response: aiohttp.ClientResponse) -> dict:
        links = {}
        if link_header := response.headers.get("Link"):
            links_raw = link_header.split(",")
            for link_desc in links_raw:
                link, rel, *_ = link_desc.strip().split(";")
                link = link.strip("<>")
                rel = rel.strip().removeprefix("rel=").strip('"')
                links[rel] = link
        return links
