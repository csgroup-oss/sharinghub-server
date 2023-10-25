import logging
import os
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

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

GITLAB_PAGINATION_HEADERS = [
    "X-Next-Page",
    "X-Page",
    "X-Per-Page",
    "X-Prev-Page",
    "X-Total",
    "X-Total-Pages",
]


class GitlabArchiveFormat(StrEnum):
    """GitLab archive formats.

    Link: https://docs.gitlab.com/ee/api/repositories.html#get-file-archive
    """

    ZIP = "zip"
    BZ2 = "bz2"
    TAR = "tar"
    TAR_BZ2 = "tar.bz2"
    TAR_GZ = "tar.gz"
    TB2 = "tb2"
    TBZ = "tbz"
    TBZ2 = "tbz2"


class GitlabPagination(TypedDict):
    page: int
    next_page: int | None
    prev_page: int | None
    per_page: int
    total: int
    total_pages: int


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


def project_url(gitlab_url: str, project: GitlabProject) -> str:
    return f"{gitlab_url.removesuffix('/')}/{project['path_with_namespace']}"


def project_issues_url(gitlab_url: str, project: GitlabProject) -> str:
    return f"{project_url(gitlab_url, project)}/issues"


class GitlabClient:
    def __init__(self, url: str, token: str, request: Request | None = None) -> None:
        self.url = url.removesuffix("/")
        self.api_url = f"{self.url}/api/v4"
        self.token = token
        self.request = request

    @staticmethod
    def _get_project_api_url(project_id: str | int) -> str:
        _project_id = urlsafe_path(str(project_id))
        return f"/projects/{_project_id}"

    def _resolve(self, endpoint: str) -> str:
        return f"{self.api_url}{endpoint}"

    async def get_projects(
        self, topic: str, page: int = 1, per_page: int = 12
    ) -> tuple[GitlabPagination, list[GitlabProject]]:
        return await self._request_paginate(
            f"/projects?topic={topic}&simple=true", page=page, per_page=per_page
        )

    async def get_project(self, project_id: str | int) -> GitlabProject:
        return await self._request(
            f"{self._get_project_api_url(project_id)}?license=true"
        )

    async def get_readme(self, project: GitlabProject) -> str:
        try:
            readme = await self._request(
                f"{self._get_project_api_url(project['id'])}/repository/files/README.md/raw",
                media_type="text",
            )
            return readme.strip()
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                raise HTTPException(
                    status_code=418, detail="Missing README.md, unprocessable project"
                ) from http_exc
            raise http_exc

    async def get_files(self, project: GitlabProject) -> list[GitlabProjectFile]:
        return [
            file
            for file in await self._request_iterate(
                f"{self._get_project_api_url(project['id'])}/repository/tree?recursive=true"
            )
            if file["type"] == "blob"
        ]

    async def get_latest_release(
        self, project: GitlabProject
    ) -> GitlabProjectRelease | None:
        try:
            return await self._request(
                f"{self._get_project_api_url(project['id'])}/releases/permalink/latest"
            )
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                return None
            raise http_exc

    async def download_file(
        self, project_id: int, ref: str, file_path: str
    ) -> StreamingResponse:
        fpath = urlsafe_path(file_path)
        project_endpoint = f"/repository/files/{fpath}/raw?ref={ref}&lfs=true"
        return await self._request_streaming(
            f"{self._get_project_api_url(project_id)}{project_endpoint}",
            filename=os.path.basename(file_path),
        )

    async def download_archive(
        self, project_id: int, ref: str, format: GitlabArchiveFormat
    ) -> StreamingResponse:
        project_endpoint = f"/repository/archive.{format}?sha={ref}"
        return await self._request_streaming(
            f"{self._get_project_api_url(project_id)}{project_endpoint}"
        )

    async def _send_request(self, url: str):
        request_headers = dict(self.request.headers) if self.request else {}
        request_headers.pop("host", None)
        request_method = self.request.method if self.request else "GET"
        request_body = await self.request.body() if self.request else None
        async with AiohttpClient() as client:
            logger.debug(f"Request {request_method}: {url}")
            response = await client.request(
                request_method,
                url,
                headers={**request_headers, "PRIVATE-TOKEN": self.token},
                data=request_body,
            )

        if not response.ok:
            raise HTTPException(
                status_code=response.status,
                detail=f"HTTP {response.status} | {request_method} {response.url}: {await response.text()}",
            )

        return response

    async def _request(
        self, endpoint: str, media_type: str = "json"
    ) -> dict[str, Any] | list[Any] | str:
        url = self._resolve(endpoint)
        response = await self._send_request(url)
        match media_type:
            case "json":
                return await response.json()
            case "text" | _:
                return await response.text()

    async def _request_streaming(
        self, endpoint: str, filename: str | None = None
    ) -> StreamingResponse:
        url = self._resolve(endpoint)
        response = await self._send_request(url)
        response_headers = dict(response.headers)

        if filename:
            default_content_disposition = [
                "attachment",
                f'filename="{filename}"',
                f"filename*=UTF-8''{filename}",
            ]
            content_disposition = response_headers.get("Content-Disposition", "").split(
                ";"
            )
            if content_disposition:
                filename_set = False
                for i, e in enumerate(content_disposition):
                    e = e.strip()
                    if e.startswith("filename=") and filename:
                        content_disposition[i] = f'filename="{filename}"'
                        filename_set = True
                    if e.startswith("filename*=UTF-8''") and filename:
                        content_disposition[i] = f"filename*=UTF-8''{filename}"
                        filename_set = True
                if not filename_set:
                    content_disposition = default_content_disposition
            else:
                content_disposition = default_content_disposition
            response_headers["Content-Disposition"] = "; ".join(content_disposition)

        return StreamingResponse(
            response.content.iter_any(),
            status_code=response.status,
            headers=response_headers,
            background=BackgroundTask(response.close),
        )

    async def _request_paginate(
        self, endpoint: str, page=1, per_page=20
    ) -> tuple[GitlabPagination, list[Any]]:
        params = {
            "page": page,
            "per_page": per_page,
            "order_by": "id",
            "sort": "asc",
        }
        url = self._resolve(endpoint)
        url = url_add_query_params(url, params)
        response = await self._send_request(url)

        items = await response.json()
        if not isinstance(items, list):
            raise HTTPException(
                status_code=422,
                detail="Unexpected: requested API do not return a list",
            )

        try:
            pagination = {
                k.lower()
                .removeprefix("x-")
                .replace("-", "_"): (
                    int(response.headers[k]) if response.headers[k] != "" else None
                )
                for k in GITLAB_PAGINATION_HEADERS
            }
        except (KeyError, TypeError) as err:
            logger.error(f"Headers: {dict(response.headers)}")
            raise HTTPException(
                status_code=500,
                detail="Missing or malformed pagination headers",
            ) from err
        return pagination, items

    async def _request_iterate(self, endpoint: str, per_page=100) -> list[Any]:
        logger.debug(f"Request iterate {endpoint}")

        params = {
            "per_page": per_page,
            "pagination": "keyset",
            "order_by": "id",
            "sort": "asc",
        }
        url = f"{self.api_url}{endpoint}"
        url = url_add_query_params(url, params)

        items = []
        while url:
            response = await self._send_request(url)

            content = await response.json()
            if not isinstance(content, list):
                raise HTTPException(
                    status_code=422,
                    detail="Unexpected: requested API do not return a list",
                )
            items.extend(content)

            links = self._get_links_from_headers(response)
            url = links.get("next") if len(content) == per_page else None

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
