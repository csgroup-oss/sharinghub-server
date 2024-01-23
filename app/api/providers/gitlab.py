import logging
import os
from typing import Any, NotRequired, TypedDict

import aiohttp
import pypandoc
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.category import get_category_from_topics
from app.utils.http import (
    AiohttpClient,
    HttpMethod,
    clean_url,
    url_add_query_params,
    urlsafe_path,
)

from .base import License, Project, ProviderClient, Release, ReleaseAsset, Topic

logger = logging.getLogger("app")


GITLAB_LICENSES_SPDX_MAPPING = {
    "agpl-3.0": License.AGPL_3_0,
    "apache-2.0": License.APACHE_2_0,
    "bsd-2-clause": License.BSD_2_CLAUSE,
    "bsd-3-clause": License.BSD_3_CLAUSE,
    "bsl-1.0": License.BSL_1_0,
    "cc0-1.0": License.CC0_1_0,
    "epl-2.0": License.EPL_2_0,
    "gpl-2.0": License.GPL_2_0,
    "gpl-3.0": License.GPL_3_0,
    "lgpl-2.1": License.LGPL_2_1,
    "mit": License.MIT,
    "mpl-2.0": License.MPL_2_0,
    "unlicense": License.UNLICENSE,
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
    readme_url: str | None
    license_url: NotRequired[str | None]
    license: NotRequired["_GitlabProjectLicense"]
    default_branch: str | None
    topics: list[str]
    star_count: int


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


class GitlabTopic(TypedDict):
    id: str
    name: str
    title: str
    description: str | None
    total_projects_count: int
    avatar_url: str | None


class GitlabClient(ProviderClient):
    def __init__(
        self, url: str, token: str, *, headers: dict[str, str] | None = None
    ) -> None:
        self.url = clean_url(url, trailing_slash=False)
        self.api_url = f"{self.url}/api"
        self.rest_url = f"{self.api_url}/v4"
        self.graphql_url = f"{self.api_url}/graphql"
        self.headers = {"Authorization": f"Bearer {token}"}
        if headers:
            self.headers |= headers

    def _rest_api(self, endpoint: str) -> str:
        endpoint = endpoint.removeprefix("/")
        return f"{self.rest_url}/{endpoint}"

    def _project_rest_api(self, project: Project, endpoint: str) -> str:
        path = urlsafe_path(project.path)
        endpoint = endpoint.removeprefix("/")
        return self._rest_api(f"/projects/{path}/{endpoint}")

    async def get_topics(self) -> list[Topic]:
        _topics: list[GitlabTopic] = await self._rest_iterate(
            url=self._rest_api("/topics")
        )
        return [Topic(**t) for t in _topics]

    async def search(self, scope: str, query: Any) -> list[Project]:
        gitlab_projects: list[GitlabProject] = await self._request(
            url=self._rest_api(f"/search"), query=dict(scope=scope, search=query)
        )
        return [_adapt_project(p) for p in gitlab_projects]

    async def get_projects(self, *topics: str) -> list[Project]:
        url = self._rest_api(f"/projects?topic={','.join(topics)}&simple=true")
        gitlab_projects: list[GitlabProject] = await self._rest_iterate(url)
        return [_adapt_project(p) for p in gitlab_projects]

    async def get_project(self, path: str) -> Project:
        path = urlsafe_path(path.strip("/"))
        url = self._rest_api(f"/projects/{path}?license=true")
        gitlab_project: GitlabProject = await self._request(url)
        return _adapt_project(gitlab_project)

    async def get_readme(self, project: Project) -> str:
        if project.readme:
            url = self._project_rest_api(
                project, f"/repository/files/{project.readme}/raw"
            )
            readme = await self._request(url, media_type="text")
            if project.readme.suffix == ".rst":
                readme = pypandoc.convert_text(readme, "md", format="rst")
            return readme.strip()
        return ""

    async def get_files(self, project: Project) -> list[str]:
        url = self._project_rest_api(project, "/repository/tree?recursive=true")
        try:
            files: list[GitlabProjectFile] = await self._rest_iterate(url)
            return [f["path"] for f in files]
        except HTTPException as http_exc:
            if http_exc.status_code != 404:
                raise http_exc
        return []

    async def get_latest_release(self, project: Project) -> Release | None:
        url = self._project_rest_api(project, "/releases/permalink/latest")
        try:
            _release: GitlabProjectRelease = await self._request(url)
            return Release(
                name=_release["name"],
                tag=_release["tag_name"],
                description=_release["description"],
                commit=_release["commit_path"].split("/")[-1],
                assets=[
                    ReleaseAsset(url=a["url"], format=a["format"])
                    for a in _release["assets"]["sources"]
                ],
            )
        except HTTPException as http_exc:
            if http_exc.status_code == 404:
                return None
            raise http_exc

    async def download_file(
        self, project_path: str, ref: str, file_path: str
    ) -> StreamingResponse:
        path = urlsafe_path(project_path.strip("/"))
        fpath = urlsafe_path(file_path)
        url = self._rest_api(
            f"/projects/{path}/repository/files/{fpath}/raw?ref={ref}&lfs=true"
        )
        return await self._request_streaming(url, filename=os.path.basename(file_path))

    async def download_archive(
        self, project_path: str, ref: str, format: str
    ) -> StreamingResponse:
        path = urlsafe_path(project_path.strip("/"))
        url = self._rest_api(f"/projects/{path}/repository/archive.{format}?sha={ref}")
        return await self._request_streaming(url)

    async def rest_proxy(self, endpoint: str, request: Request) -> StreamingResponse:
        url = self._rest_api(endpoint)
        return await self._request_streaming(url, request=request)

    async def _request(
        self, url: str, media_type: str = "json", **params: Any
    ) -> dict[str, Any] | list[Any] | str | None:
        response = await self._send_request(url, **params)
        match media_type:
            case "json":
                return await response.json()
            case "text" | _:
                return await response.text()

    async def _request_streaming(
        self, url: str, filename: str | None = None, request: Request | None = None
    ) -> StreamingResponse:
        response = await self._send_request(url, request=request)
        response_headers = dict(response.headers)
        response_headers.pop("Content-Encoding", None)

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
        )

    async def _rest_iterate(self, url: str, per_page=100) -> list[Any]:
        logger.debug(f"Request iterate {url}")

        params = {
            "per_page": per_page,
            "pagination": "keyset",
            "order_by": "id",
            "sort": "asc",
        }
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

    async def _send_request(
        self,
        url: str,
        *,
        method: HttpMethod = HttpMethod.GET,
        query: dict[str, Any] | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
        request: Request | None = None,
    ) -> aiohttp.ClientResponse:
        if query is None:
            query = {}
        if headers is None:
            headers = {}
        if request:
            method = request.method.upper()
            query |= dict(request.query_params)
            body = await request.body()
            headers |= dict(request.headers)

        remove_headers = ["host", "cookie"]
        headers = {
            k: v
            for k, v in headers.items()
            if k not in remove_headers and not k.startswith("x-")
        }
        query.pop("gitlab_token", None)

        url = url_add_query_params(url, query)
        headers = self.headers | headers
        async with AiohttpClient() as client:
            logger.debug(f"Request {method}: {url}")
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
            )

        if not response.ok:
            raise HTTPException(
                status_code=response.status,
                detail=f"HTTP {response.status} | {method} {response.url}: {await response.text()}",
            )

        return response


def _adapt_project(gitlab_project: GitlabProject) -> Project:
    if gitlab_project["readme_url"]:
        readme_path = gitlab_project["readme_url"].replace(
            f"{gitlab_project['web_url']}/-/blob/{gitlab_project['default_branch']}/",
            "",
        )
    else:
        readme_path = None

    if gitlab_project.get("license"):
        license_id = GITLAB_LICENSES_SPDX_MAPPING.get(gitlab_project["license"]["key"])
    else:
        license_id = None

    category = get_category_from_topics(gitlab_project["topics"])

    return Project(
        id=gitlab_project["id"],
        name=gitlab_project["name"],
        full_name=gitlab_project["name_with_namespace"],
        path=gitlab_project["path_with_namespace"],
        description=gitlab_project["description"],
        url=gitlab_project["web_url"],
        issues_url=gitlab_project["web_url"] + "/issues",
        created_at=gitlab_project["created_at"],
        last_update=gitlab_project["last_activity_at"],
        star_count=gitlab_project["star_count"],
        topics=gitlab_project["topics"],
        category=category,
        default_branch=gitlab_project["default_branch"],
        readme=readme_path,
        license_id=license_id,
        license_url=gitlab_project.get("license_url"),
    )
