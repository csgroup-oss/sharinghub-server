import json
import logging
import os
from datetime import datetime
from typing import Any, NotRequired, TypedDict

import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from shapely.geometry.base import BaseGeometry

from app.stac.api.category import get_category_from_topics
from app.utils import geo
from app.utils import markdown as md
from app.utils.http import (
    AiohttpClient,
    HttpMethod,
    clean_url,
    url_add_query_params,
    urlsafe_path,
)

from ..schemas import License, Project, ProjectPreview, ProjectReference, Release, Topic
from ._base import CursorPagination, ProviderClient

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


class GitlabREST_Project(TypedDict):
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
    license: NotRequired["_GitlabREST_ProjectLicense"]
    default_branch: str | None
    topics: list[str]
    star_count: int


class _GitlabREST_ProjectLicense(TypedDict):
    key: str
    name: str
    html_url: str


class GitlabREST_ProjectFile(TypedDict):
    id: str
    name: str
    path: str


class GitlabREST_ProjectRelease(TypedDict):
    name: str
    tag_name: str
    description: str
    commit_path: str
    tag_path: str
    assets: "_GitlabREST_ProjectReleaseAssets"


class _GitlabREST_ProjectReleaseAssets(TypedDict):
    count: int
    sources: list["_GitlabREST_ProjectReleaseSources"]


class _GitlabREST_ProjectReleaseSources(TypedDict):
    format: str
    url: str


class GitlabREST_Topic(TypedDict):
    id: str
    name: str
    title: str
    description: str | None
    total_projects_count: int
    avatar_url: str | None


class GitlabGraphQL_ProjectReference(TypedDict):
    id: str
    name: str
    fullPath: str
    topics: list[str]


class GitlabGraphQL_ProjectPreview(GitlabGraphQL_ProjectReference):
    description: str | None
    createdAt: str
    lastActivityAt: str
    starCount: int
    repository: "_GitlabGraphQL_Repository1"
    _metadata: NotRequired[dict[str, Any]]
    _readme: NotRequired[str]


class GitlabGraphQL_Project(GitlabGraphQL_ProjectPreview):
    nameWithNamespace: str
    webUrl: str
    repository: "_GitlabGraphQL_Repository2"
    releases: "_GitlabGraphQL_Releases"


class _GitlabGraphQL_Repository1(TypedDict):
    rootRef: str | None
    blobs: "_GitlabGraphQL_RepositoryBlobs"


class _GitlabGraphQL_RepositoryBlobs(TypedDict):
    nodes: list["_GitlabGraphQL_RepositoryBlobNode"]


class _GitlabGraphQL_RepositoryBlobNode(TypedDict):
    rawBlob: str


class _GitlabGraphQL_Repository2(_GitlabGraphQL_Repository1):
    tree: "_GitlabGraphQL_Tree"


class _GitlabGraphQL_Tree(TypedDict):
    lastCommit: "_GitlabGraphQL_Commit"
    blobs: "_GitlabGraphQL_TreeBlobs"


class _GitlabGraphQL_Commit(TypedDict):
    shortId: str


class _GitlabGraphQL_TreeBlobs(TypedDict):
    nodes: list["_GitlabGraphQL_TreeBlobNode"]


class _GitlabGraphQL_TreeBlobNode(TypedDict):
    path: str


class _GitlabGraphQL_Releases(TypedDict):
    nodes: list["_GitlabGraphQL_Release"]


class _GitlabGraphQL_Release(TypedDict):
    name: str
    tagName: str
    description: str
    commit: "_GitlabGraphQL_ReleaseCommit"


class _GitlabGraphQL_ReleaseCommit(TypedDict):
    sha: str


GITLAB_GRAPHQL_SORTS = ["id", "name", "created", "updated", "stars"]
GITLAB_GRAPHQL_SORTS_ALIASES = {
    "title": "name",
    "datetime": "updated",
    "start_datetime": "created",
    "end_datetime": "updated",
}
GITLAB_GRAPHQL_REQUEST_MAX_SIZE = 100


GITLAB_GRAPHQL_PROJECT_REFERENCE_FRAGMENT = """
fragment projectFields on Project {
  id
  name
  fullPath
  topics
}
"""
GITLAB_GRAPHQL_PROJECT_PREVIEW_FRAGMENT = """
fragment projectFields on Project {
  id
  name
  fullPath
  description
  createdAt
  lastActivityAt
  starCount
  topics
  repository {
    rootRef
    blobs(paths: ["README.md"]) {
      nodes {
        rawBlob
      }
    }
  }
}
"""
GITLAB_GRAPHQL_PROJECT_FRAGMENT = """
fragment projectFields on Project {
  id
  name
  nameWithNamespace
  fullPath
  description
  webUrl
  createdAt
  lastActivityAt
  starCount
  topics
  repository {
    rootRef
    blobs(paths: ["README.md"]) {
      nodes {
        rawBlob
      }
    }
    tree(path: "/", recursive: true) {
      lastCommit {
        shortId
      }
      blobs {
        nodes {
          path
        }
      }
    }
  }
  releases(first: 1) {
    nodes {
      name
      tagName
      description
      commit {
        sha
      }
    }
  }
}
"""


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

    async def get_topics(self) -> list[Topic]:
        _topics: list[GitlabREST_Topic] = await self._rest_iterate(
            url=self._resolve_rest_api_url("/topics")
        )
        return [Topic(**t) for t in _topics]

    async def get_project_from_id(self, id: int) -> Project:
        rest_project_data = await self._get_project_rest(str(id))
        project_path = rest_project_data["path_with_namespace"]
        return await self.get_project(project_path)

    async def get_project(self, path: str) -> Project:
        path = path.strip("/")
        graphql_query = f"""
        query getProject {{
            project(fullPath: "{path}") {{
                ...projectFields
            }}
        }}
        {GITLAB_GRAPHQL_PROJECT_FRAGMENT}
        """
        graphql_project_req = await self._graphql(graphql_query)
        graphql_project_data = graphql_project_req["data"]["project"]
        if not graphql_project_data:
            raise HTTPException(status_code=404)
        return _adapt_graphql_project(graphql_project_data)

    async def get_license(self, project: ProjectReference) -> License | None:
        rest_project_data = await self._get_project_rest(project.path)

        _license_url = rest_project_data["license_url"]
        _license = rest_project_data["license"]
        if _license and _license_url:
            license_id = GITLAB_LICENSES_SPDX_MAPPING.get(
                _license["key"], _license["key"].upper()
            )
            return License(id=license_id, url=_license_url)
        return None

    async def _get_project_rest(self, path_or_id: str) -> GitlabREST_Project:
        path_or_id = urlsafe_path(path_or_id.strip("/"))
        url = self._resolve_rest_api_url(f"/projects/{path_or_id}?license=true")
        return await self._request(url)

    async def search_references(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        limit: int,
        sort: tuple[str, str] | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[ProjectReference], CursorPagination]:
        _projects, pagination = await self._search(
            project_fragment=GITLAB_GRAPHQL_PROJECT_REFERENCE_FRAGMENT,
            ids=ids,
            query=query,
            topics=topics,
            flags=flags,
            extent=None,
            datetime_range=None,
            limit=limit,
            sort=sort,
            prev=prev,
            next=next,
        )
        projects = [_adapt_graphql_project_reference(p) for p in _projects]
        return projects, pagination

    async def search_previews(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        extent: BaseGeometry | None,
        datetime_range: tuple[datetime, datetime] | None,
        limit: int,
        sort: tuple[str, str] | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[ProjectPreview], CursorPagination]:
        _projects, pagination = await self._search(
            project_fragment=GITLAB_GRAPHQL_PROJECT_PREVIEW_FRAGMENT,
            ids=ids,
            query=query,
            topics=topics,
            flags=flags,
            extent=extent,
            datetime_range=datetime_range,
            limit=limit,
            sort=sort,
            prev=prev,
            next=next,
        )
        projects = [_adapt_graphql_project_preview(p) for p in _projects]
        return projects, pagination

    async def search(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        extent: BaseGeometry | None,
        datetime_range: tuple[datetime, datetime] | None,
        limit: int,
        sort: tuple[str, str] | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[Project], CursorPagination]:
        _projects, pagination = await self._search(
            project_fragment=GITLAB_GRAPHQL_PROJECT_FRAGMENT,
            ids=ids,
            query=query,
            topics=topics,
            flags=flags,
            extent=extent,
            datetime_range=datetime_range,
            limit=limit,
            sort=sort,
            prev=prev,
            next=next,
        )
        projects = [_adapt_graphql_project(p) for p in _projects]
        return projects, pagination

    async def _search(
        self,
        project_fragment: str,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        extent: BaseGeometry | None,
        datetime_range: tuple[datetime, datetime] | None,
        limit: int,
        sort: tuple[str, str] | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[dict[str, Any]], CursorPagination]:
        if ids:
            projects = await self._search_projects_by_ids(project_fragment, ids)

            # Filter by topics
            _topics = set(topics)
            projects = [p for p in projects if _topics.issubset(p["topics"])]

            pagination = CursorPagination(total=len(ids), start=None, end=None)
            return projects, pagination

        if prev:
            cursor = prev
            direction = -1
        else:
            cursor = next
            direction = 1

        local_filtering = any((extent, datetime_range, flags))
        search_size = limit if not local_filtering else limit + 1

        req_limit = limit if not local_filtering else GITLAB_GRAPHQL_REQUEST_MAX_SIZE
        req_params = {
            "query": query,
            "topics": topics,
            "limit": req_limit,
            "sort": sort,
            "direction": direction,
        }

        # Flags
        starred = "starred" in flags

        projects_cur: list[tuple[str, dict[str, Any]]] = []
        paginations: list[CursorPagination] = []

        _stop = False
        while len(projects_cur) < search_size and not _stop:
            if not starred:
                _projects_cur, _pagination = await self._search_projects(
                    project_fragment, **req_params, cursor=cursor
                )
            else:
                _projects_cur, _pagination = await self._search_starred_projects(
                    project_fragment, **req_params, cursor=cursor
                )

                # Filter by topics
                _topics = set(topics)
                _projects_cur = [
                    _pc for _pc in _projects_cur if _topics.issubset(_pc[1]["topics"])
                ]

            if datetime_range:

                def temporal_check(project_data: GitlabGraphQL_Project) -> bool:
                    created_at = datetime.fromisoformat(project_data["createdAt"])
                    updated_at = datetime.fromisoformat(project_data["lastActivityAt"])
                    return (
                        datetime_range[0] <= created_at <= datetime_range[1]
                        or datetime_range[0] <= updated_at <= datetime_range[1]
                        or created_at
                        <= datetime_range[0]
                        <= datetime_range[1]
                        <= updated_at
                    )

                _projects_cur = [_pc for _pc in _projects_cur if temporal_check(_pc[1])]

            if extent:

                def spatial_check(project_data: GitlabGraphQL_Project) -> bool:
                    if project_extent := _process_spatial_extent(project_data):
                        return extent.intersects(project_extent)
                    return False

                _projects_cur = [_pc for _pc in _projects_cur if spatial_check(_pc[1])]

            # ---------------------- #

            if direction > 0:
                projects_cur = [*projects_cur, *_projects_cur]
                cursor = _pagination["end"]
            else:
                projects_cur = [*_projects_cur, *projects_cur]
                cursor = _pagination["start"]

            paginations.append(_pagination)

            if not cursor:
                _stop = True

        if projects_cur:
            if direction > 0:
                projects_cur, _left = projects_cur[:limit], projects_cur[limit:]
                start_cursor = projects_cur[0][0] if paginations[0]["start"] else None
                end_cursor = projects_cur[-1][0] if _left else paginations[-1]["end"]
            else:
                _left, projects_cur = projects_cur[:-limit], projects_cur[-limit:]
                start_cursor = projects_cur[0][0] if _left else paginations[-1]["start"]
                end_cursor = projects_cur[-1][0] if paginations[0]["end"] else None
        else:
            logger.debug(
                f"Could not find any project {'after' if direction > 0 else 'before'}: "
                f"{prev if prev else next} "
                f"({query=}, {topics=}, {limit=}, {datetime_range=} {extent=})"
            )
            start_cursor = None
            end_cursor = None

        projects = [p[1] for p in projects_cur]
        count_projects = len(projects)
        pagination = CursorPagination(
            total=(
                paginations[0]["total"]
                if not local_filtering
                else (
                    count_projects
                    if (count_projects < limit and not any((prev, next)))
                    or (count_projects == limit and not end_cursor)
                    else None
                )
            ),
            start=start_cursor,
            end=end_cursor,
        )
        return projects, pagination

    async def _search_projects_by_ids(
        self, project_fragment: str, ids: list[str]
    ) -> list[dict[str, Any]]:
        graphql_query = "\n".join(
            f'project{i}: project(fullPath: "{id_}") {{...projectFields }}'
            for i, id_ in enumerate(ids)
        )
        graphql_query = f"""
        query getProjectsByIds {{
            {graphql_query}
        }}
        {project_fragment}
        """
        result = await self._graphql(graphql_query)
        data = result["data"]
        return [p for p in data.values()]

    async def _search_projects(
        self,
        project_fragment: str,
        query: str | None,
        topics: list[str],
        limit: int,
        sort: tuple[str, str] | None,
        cursor: str | None,
        direction: int,
    ) -> tuple[list[tuple[str, dict[str, Any]]], CursorPagination]:
        limit_param, cursor_param = self._get_graphql_cursor_params(direction)

        graphql_sort = self._get_graphql_sort(sort)
        graphql_variables: dict[str, Any] = {
            "limit": limit,
            "sortby": graphql_sort,
            "cursor": cursor,
        }
        graphql_query_params: dict[str, tuple[str, str]] = {
            "limit": ("Int", limit_param),
            "sortby": ("String", "sort"),
            "cursor": ("String", cursor_param),
        }

        if query:
            graphql_query_params["search"] = ("String!", "search")
            graphql_variables["search"] = query
        if topics:
            graphql_query_params["topics"] = ("[String!]", "topics")
            graphql_variables["topics"] = topics

        _params_definition = ", ".join(
            f"${p}: {graphql_query_params[p][0]}" for p in graphql_query_params
        )
        _params = ", ".join(
            f"{graphql_query_params[p][1]}: ${p}" for p in graphql_query_params
        )
        graphql_query = f"""
        query searchProjects({_params_definition}) {{
            search: projects({_params}) {{
                edges {{
                    cursor
                    node {{
                        ...projectFields
                    }}
                }}
                pageInfo {{
                    hasPreviousPage
                    hasNextPage
                    startCursor
                    endCursor
                }}
                count
            }}
        }}
        {project_fragment}
        """
        logger.debug(f"GraphQL searchProjects: {graphql_variables}")
        result = await self._graphql(graphql_query, variables=graphql_variables)
        data = result["data"]["search"]

        page_info = data["pageInfo"]
        pagination = CursorPagination(
            total=data["count"],
            start=page_info["startCursor"] if page_info["hasPreviousPage"] else None,
            end=page_info["endCursor"] if page_info["hasNextPage"] else None,
        )
        projects_cur: list[tuple[str, GitlabGraphQL_Project]] = [
            (e["cursor"], e["node"]) for e in data["edges"]
        ]
        return projects_cur, pagination

    async def _search_starred_projects(
        self,
        project_fragment: str,
        query: str | None,
        limit: int,
        cursor: str | None,
        direction: int,
        **kwargs: Any,
    ) -> tuple[list[tuple[str, dict[str, Any]]], CursorPagination]:
        limit_param, cursor_param = self._get_graphql_cursor_params(direction)
        graphql_variables: dict[str, Any] = {
            "limit": limit,
            "cursor": cursor,
        }
        graphql_query_params: dict[str, tuple[str, str]] = {
            "limit": ("Int", limit_param),
            "cursor": ("String", cursor_param),
        }
        if query:
            graphql_query_params["search"] = ("String!", "search")
            graphql_variables["search"] = query

        _params_definition = ", ".join(
            f"${p}: {graphql_query_params[p][0]}" for p in graphql_query_params
        )
        _params = ", ".join(
            f"{graphql_query_params[p][1]}: ${p}" for p in graphql_query_params
        )
        graphql_query = f"""
        query searchStarredProjects({_params_definition}) {{
            currentUser {{
                starredProjects({_params}) {{
                    edges {{
                        cursor
                        node {{
                            ...projectFields
                        }}
                    }}
                    pageInfo {{
                        hasPreviousPage
                        hasNextPage
                        startCursor
                        endCursor
                    }}
                    count
                }}
            }}
        }}
        {project_fragment}
        """
        logger.debug(f"GraphQL searchStarredProjects: {graphql_variables}")
        result = await self._graphql(graphql_query, variables=graphql_variables)
        data = result["data"]["currentUser"]["starredProjects"]

        page_info = data["pageInfo"]
        pagination = CursorPagination(
            total=data["count"],
            start=page_info["startCursor"] if page_info["hasPreviousPage"] else None,
            end=page_info["endCursor"] if page_info["hasNextPage"] else None,
        )
        projects_cur: list[tuple[str, GitlabGraphQL_Project]] = [
            (e["cursor"], e["node"]) for e in data["edges"]
        ]
        return projects_cur, pagination

    def _get_graphql_cursor_params(self, direction) -> tuple[str, str]:
        if direction > 0:
            limit_param = "first"
            cursor_param = "after"
        else:
            limit_param = "last"
            cursor_param = "before"
        return limit_param, cursor_param

    def _get_graphql_sort(self, sort: tuple[str, str] | None) -> tuple[str, str]:
        if sort:
            sort_field, sort_direction = sort
            if sort_field not in GITLAB_GRAPHQL_SORTS:
                sort_field = GITLAB_GRAPHQL_SORTS_ALIASES.get(
                    sort_field, GITLAB_GRAPHQL_SORTS[0]
                )
        else:
            sort_direction = "asc"
            sort_field = GITLAB_GRAPHQL_SORTS[0]
        return f"{sort_field}_{sort_direction}"

    async def download_file(
        self,
        project_path: str,
        ref: str,
        file_path: str,
        file_cache: int,
        request: Request,
    ) -> StreamingResponse:
        path = urlsafe_path(project_path.strip("/"))
        fpath = urlsafe_path(file_path)
        url = self._resolve_rest_api_url(
            f"/projects/{path}/repository/files/{fpath}/raw?ref={ref}&lfs=true"
        )
        return await self._request_streaming(
            url,
            filename=os.path.basename(file_path),
            file_cache=file_cache,
            request=request,
        )

    async def download_archive(
        self, project_path: str, ref: str, format: str, request: Request
    ) -> StreamingResponse:
        path = urlsafe_path(project_path.strip("/"))
        url = self._resolve_rest_api_url(
            f"/projects/{path}/repository/archive.{format}?sha={ref}"
        )
        return await self._request_streaming(url, request=request)

    async def rest_proxy(self, endpoint: str, request: Request) -> StreamingResponse:
        url = self._resolve_rest_api_url(endpoint)
        return await self._request_streaming(url, request=request)

    def _resolve_rest_api_url(self, endpoint: str) -> str:
        endpoint = endpoint.removeprefix("/")
        return f"{self.rest_url}/{endpoint}"

    async def _graphql(
        self, query: str, *, variables: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any] | str | None:
        return await self._request(
            url=self.graphql_url,
            media_type="json",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"query": query, "variables": variables}),
        )

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
        self,
        url: str,
        filename: str | None = None,
        file_cache: int | None = None,
        request: Request | None = None,
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

            if file_cache:
                response_headers["Cache-Control"] = f"private, max-age={file_cache}"

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
        headers: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
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
        method = method.upper()
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


def _adapt_graphql_project_reference(
    project_data: GitlabGraphQL_ProjectReference,
) -> ProjectReference:
    return ProjectReference(
        id=int(project_data["id"].split("/")[-1]),
        name=project_data["name"],
        path=project_data["fullPath"],
        topics=project_data["topics"],
        category=get_category_from_topics(project_data["topics"]),
    )


def _adapt_graphql_project_preview(
    project_data: GitlabGraphQL_ProjectPreview,
) -> ProjectPreview:
    readme, metadata = _process_readme_and_metadata(project_data, save=False)
    extent = _process_spatial_extent(project_data, save=False)
    return ProjectPreview(
        id=int(project_data["id"].split("/")[-1]),
        name=project_data["name"],
        path=project_data["fullPath"],
        description=project_data["description"],
        topics=project_data["topics"],
        category=get_category_from_topics(project_data["topics"]),
        created_at=project_data["createdAt"],
        last_update=project_data["lastActivityAt"],
        star_count=project_data["starCount"],
        default_branch=project_data["repository"]["rootRef"],
        readme=readme,
        metadata=metadata,
        extent=extent,
    )


def _adapt_graphql_project(project_data: GitlabGraphQL_Project) -> Project:
    readme, metadata = _process_readme_and_metadata(project_data, save=False)
    extent = _process_spatial_extent(project_data, save=False)

    if project_data["repository"]["tree"]:
        last_commit = project_data["repository"]["tree"]["lastCommit"]["shortId"]
        files = [
            n["path"] for n in project_data["repository"]["tree"]["blobs"]["nodes"]
        ]
    else:
        last_commit = None
        files = None

    if project_data["releases"]["nodes"]:
        _release = project_data["releases"]["nodes"][0]
        release = Release(
            name=_release["name"],
            tag=_release["tagName"],
            description=_release["description"],
            commit=_release["commit"]["sha"],
        )
    else:
        release = None

    return Project(
        id=int(project_data["id"].split("/")[-1]),
        name=project_data["name"],
        full_name=project_data["nameWithNamespace"],
        path=project_data["fullPath"],
        description=project_data["description"],
        topics=project_data["topics"],
        url=project_data["webUrl"],
        bug_tracker=project_data["webUrl"] + "/issues",
        category=get_category_from_topics(project_data["topics"]),
        created_at=project_data["createdAt"],
        last_update=project_data["lastActivityAt"],
        star_count=project_data["starCount"],
        default_branch=project_data["repository"]["rootRef"],
        readme=readme,
        metadata=metadata,
        extent=extent,
        license=None,
        last_commit=last_commit,
        files=files,
        latest_release=release,
    )


def _process_readme_and_metadata(
    project_data: GitlabGraphQL_ProjectPreview, save: bool = True
) -> tuple[str, dict]:
    if all(e in project_data for e in ["_readme", "_metadata"]):
        readme, metadata = project_data["_readme"], project_data["_metadata"]
    elif project_data["repository"]["blobs"]["nodes"]:
        readme, metadata = md.parse(
            project_data["repository"]["blobs"]["nodes"][0]["rawBlob"]
        )
        if save:
            project_data["_readme"] = readme
            project_data["_metadata"] = metadata
    else:
        readme, metadata = "", {}
    return readme, metadata


def _process_spatial_extent(
    project_data: GitlabGraphQL_ProjectPreview, save: bool = True
) -> BaseGeometry | None:
    if "_extent" in project_data:
        return project_data["_extent"]

    _, metadata = _process_readme_and_metadata(project_data, save=save)
    if extent_src := metadata.get("extent", {}).get("spatial"):
        if isinstance(extent_src, list) and len(extent_src) == 4:
            extent = geo.bbox2geom(extent_src)
        elif isinstance(extent_src, str):
            extent = geo.wkt2geom(extent_src)
        else:
            extent = None

        if extent and save:
            project_data["_extent"] = extent
        return extent
    return None
