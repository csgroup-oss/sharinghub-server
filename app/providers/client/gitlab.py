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
import logging
import os
from datetime import datetime
from typing import Any, NotRequired, TypedDict, cast, no_type_check

import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic_core import Url
from shapely.geometry.base import BaseGeometry
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from app.providers.schemas import (
    AccessLevel,
    License,
    MLflow,
    Project,
    ProjectPreview,
    ProjectReference,
    Release,
    Topic,
)
from app.settings import MLFLOW_URL
from app.stac.api.category import FeatureVal, get_categories_from_topics
from app.utils import geo
from app.utils import markdown as md
from app.utils.http import (
    AiohttpClient,
    HttpMethod,
    clean_url,
    url_add_query_params,
    urlsafe_path,
)

from ._base import CursorPagination, ProviderClient

logger = logging.getLogger("app")


BBOX_LEN = 4

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

GUEST_ACCESS_LEVEL = 10
DEVELOPER_ACCESS_LEVEL = 30
MAINTAINER_ACCESS_LEVEL = 40


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
    name: str
    title: str
    total_projects_count: int


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
    _extent: NotRequired[BaseGeometry]


class GitlabGraphQL_Project(GitlabGraphQL_ProjectReference):
    description: str | None
    createdAt: str
    lastActivityAt: str
    starCount: int
    nameWithNamespace: str
    webUrl: str
    repository: "_GitlabGraphQL_Repository2"
    releases: "_GitlabGraphQL_Releases"
    maxAccessLevel: "_GitlabGraphQL_AccessLevel"
    _metadata: NotRequired[dict[str, Any]]
    _readme: NotRequired[str]
    _extent: NotRequired[BaseGeometry]


class _GitlabGraphQL_Repository1(TypedDict):
    rootRef: str | None
    readme: "_GitlabGraphQL_RepositoryRawBlobs"
    preview: "_GitlabGraphQL_RepositoryPathBlobs"


class _GitlabGraphQL_Repository2(TypedDict):
    rootRef: str | None
    readme: "_GitlabGraphQL_RepositoryRawBlobs"
    preview: "_GitlabGraphQL_RepositoryPathBlobs"
    tree: "_GitlabGraphQL_Tree"


class _GitlabGraphQL_RepositoryRawBlobs(TypedDict):
    nodes: list["_GitlabGraphQL_RepositoryRawBlobNode"]


class _GitlabGraphQL_RepositoryRawBlobNode(TypedDict):
    rawBlob: str


class _GitlabGraphQL_RepositoryPathBlobs(TypedDict):
    nodes: list["_GitlabGraphQL_RepositoryPathBlobNode"]


class _GitlabGraphQL_RepositoryPathBlobNode(TypedDict):
    path: str


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


class _GitlabGraphQL_AccessLevel(TypedDict):
    integerValue: int


class _QueryDataEdge(TypedDict):
    cursor: str
    node: dict[str, Any]


class _QueryDataPageInfo(TypedDict):
    hasPreviousPage: bool
    hasNextPage: bool
    startCursor: str | None
    endCursor: str | None


class _QueryData(TypedDict):
    edges: list[_QueryDataEdge]
    pageInfo: _QueryDataPageInfo
    count: int


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
    readme: blobs(paths: ["README.md", "readme.md"]) {
      nodes {
        rawBlob
      }
    }
    preview: blobs(paths: ["preview.png", "preview.jpg", "preview.jpeg"]) {
      nodes {
        path
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
  maxAccessLevel {
    integerValue
  }
  repository {
    rootRef
    readme: blobs(paths: ["README.md", "readme.md"]) {
      nodes {
        rawBlob
      }
    }
    preview: blobs(paths: ["preview.png", "preview.jpg", "preview.jpeg"]) {
      nodes {
        path
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
        self,
        url: str,
        token: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = clean_url(url, trailing_slash=False)
        self.api_url = f"{self.url}/api"
        self.rest_url = f"{self.api_url}/v4"
        self.graphql_url = f"{self.api_url}/graphql"
        self.headers = {"Authorization": f"Bearer {token}"}
        if headers:
            self.headers |= headers

    async def get_user(self) -> str:
        graphql_query = """
        query {
            currentUser {
                username
            }
        }
        """
        graphql_req = await self._graphql(graphql_query)
        if not isinstance(graphql_req, dict):
            detail = "Unexpected response from GitLab"
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
            )

        graphql_data: dict[str, Any] = graphql_req["data"]
        return graphql_data["currentUser"]["username"]

    async def get_topics(self) -> list[Topic]:
        _topics: list[GitlabREST_Topic] = await self._rest_iterate(
            url=self._resolve_rest_api_url("/topics"),
        )
        return [Topic(**t) for t in _topics]

    async def get_project_path(self, id: int) -> str:
        try:
            rest_project_data = await self._get_project_rest(str(id))
        except HTTPException as err:
            if err.status_code == HTTP_404_NOT_FOUND:
                err.detail = "Not Found"
            raise
        return rest_project_data["path_with_namespace"]

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
        graphql_req = await self._graphql(graphql_query)
        if not isinstance(graphql_req, dict):
            detail = "Unexpected response from GitLab"
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
            )

        graphql_data: dict[str, Any] = graphql_req["data"]
        project_data: GitlabGraphQL_Project = graphql_data["project"]
        if not project_data:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND)

        return _adapt_graphql_project(project_data)

    async def get_license(self, project: ProjectReference) -> License | None:
        rest_project_data = await self._get_project_rest(project.path)

        _license_url = rest_project_data["license_url"]
        _license = rest_project_data["license"]
        if _license and _license_url:
            license_id = GITLAB_LICENSES_SPDX_MAPPING.get(
                _license["key"],
                _license["key"].upper(),
            )
            return License(id=license_id, url=Url(_license_url))
        return None

    async def _get_project_rest(self, path_or_id: str) -> GitlabREST_Project:
        path_or_id = urlsafe_path(path_or_id.strip("/"))
        url = self._resolve_rest_api_url(f"/projects/{path_or_id}?license=true")
        rest_req = await self._request(url)
        if not isinstance(rest_req, dict):
            detail = "Unexpected response from GitLab"
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
            )
        return cast(GitlabREST_Project, rest_req)

    async def search_references(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        limit: int,
        sort: tuple[str, str] | None,
        start: str | None,
        end: str | None,
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
            start=start,
            end=end,
        )
        projects = [
            _adapt_graphql_project_reference(p)
            for p in cast(list[GitlabGraphQL_ProjectReference], _projects)
        ]
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
        start: str | None,
        end: str | None,
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
            start=start,
            end=end,
        )
        projects = [
            _adapt_graphql_project_preview(p)
            for p in cast(list[GitlabGraphQL_ProjectPreview], _projects)
        ]
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
        start: str | None,
        end: str | None,
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
            start=start,
            end=end,
        )
        projects = [
            _adapt_graphql_project(p)
            for p in cast(list[GitlabGraphQL_Project], _projects)
        ]
        return projects, pagination

    async def _search(  # noqa: C901
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
        start: str | None,
        end: str | None,
    ) -> tuple[list[dict[str, Any]], CursorPagination]:
        if ids:
            projects = await self._search_projects_by_ids(project_fragment, ids)

            # Filter-out not found
            projects = [p for p in projects if p is not None]

            # Filter by topics
            _topics = set(topics)
            projects = [p for p in projects if _topics.issubset(p["topics"])]

            pagination = CursorPagination(total=len(ids), start=None, end=None)
            return projects, pagination

        cursor: str | None
        if end:
            cursor = end
            direction = -1
        else:
            cursor = start
            direction = 1

        local_filtering = any((extent, datetime_range, flags))
        search_size = limit if not local_filtering else limit + 1
        req_limit = limit if not local_filtering else GITLAB_GRAPHQL_REQUEST_MAX_SIZE

        # Flags
        starred = "starred" in flags

        projects_cur: list[tuple[str, dict[str, Any]]] = []
        paginations: list[CursorPagination] = []

        _stop = False
        while len(projects_cur) < search_size and not _stop:
            if not starred:
                _projects_cur, _pagination = await self._search_projects(
                    project_fragment,
                    query=query,
                    topics=topics,
                    limit=req_limit,
                    sort=sort,
                    cursor=cursor,
                    direction=direction,
                )
            else:
                _projects_cur, _pagination = await self._search_starred_projects(
                    project_fragment,
                    query=query,
                    topics=topics,
                    limit=req_limit,
                    cursor=cursor,
                    direction=direction,
                )

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

                _projects_cur = [_pc for _pc in _projects_cur if temporal_check(_pc[1])]  # type: ignore[arg-type]

            if extent:

                def spatial_check(project_data: GitlabGraphQL_Project) -> bool:
                    if project_extent := _process_spatial_extent(project_data):  # type: ignore[arg-type]
                        return extent.intersects(project_extent)
                    return False

                _projects_cur = [_pc for _pc in _projects_cur if spatial_check(_pc[1])]  # type: ignore[arg-type]

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
                f"{end if end else start} "
                f"({query=}, {topics=}, {limit=}, {datetime_range=} {extent=})",
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
                    if (count_projects < limit and not any((start, end)))
                    or (count_projects == limit and not end_cursor)
                    else None
                )
            ),
            start=start_cursor,
            end=end_cursor,
        )
        return projects, pagination

    async def _search_projects_by_ids(
        self,
        project_fragment: str,
        ids: list[str],
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
        data: dict[str, dict[str, Any]] = result["data"]  # type: ignore[index, assignment, call-overload]
        return list(data.values())

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
        data: _QueryData = result["data"]["search"]  # type: ignore[index, assignment, call-overload]

        page_info = data["pageInfo"]
        pagination = CursorPagination(
            total=data["count"],
            start=page_info["startCursor"] if page_info["hasPreviousPage"] else None,
            end=page_info["endCursor"] if page_info["hasNextPage"] else None,
        )
        projects_cur: list[tuple[str, dict[str, Any]]] = [
            (e["cursor"], e["node"]) for e in data["edges"]
        ]
        return projects_cur, pagination

    async def _search_starred_projects(
        self,
        project_fragment: str,
        query: str | None,
        topics: list[str],
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
        data: _QueryData = result["data"]["currentUser"]["starredProjects"]  # type: ignore[index, assignment, call-overload]

        page_info = data["pageInfo"]
        pagination = CursorPagination(
            total=data["count"],
            start=page_info["startCursor"] if page_info["hasPreviousPage"] else None,
            end=page_info["endCursor"] if page_info["hasNextPage"] else None,
        )
        _topics = set(topics)
        projects_cur: list[tuple[str, dict[str, Any]]] = [
            (e["cursor"], e["node"])
            for e in data["edges"]
            if _topics.issubset(e["node"]["topics"])  # type: ignore[index]
        ]
        return projects_cur, pagination

    def _get_graphql_cursor_params(self, direction: int) -> tuple[str, str]:
        if direction > 0:
            limit_param = "first"
            cursor_param = "after"
        else:
            limit_param = "last"
            cursor_param = "before"
        return limit_param, cursor_param

    def _get_graphql_sort(self, sort: tuple[str, str] | None) -> str:
        if sort:
            sort_field, sort_direction = sort
            if sort_field not in GITLAB_GRAPHQL_SORTS:
                sort_field = GITLAB_GRAPHQL_SORTS_ALIASES.get(
                    sort_field,
                    GITLAB_GRAPHQL_SORTS[0],
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
            f"/projects/{path}/repository/files/{fpath}/raw?ref={ref}&lfs=true",
        )
        return await self._request_streaming(
            url,
            filename=os.path.basename(file_path),
            file_cache=file_cache,
            request=request,
        )

    async def download_archive(
        self,
        project_path: str,
        ref: str,
        archive_format: str,
        request: Request,
    ) -> StreamingResponse:
        path = urlsafe_path(project_path.strip("/"))
        url = self._resolve_rest_api_url(
            f"/projects/{path}/repository/archive.{archive_format}?sha={ref}",
        )
        return await self._request_streaming(url, request=request)

    async def rest_proxy(self, endpoint: str, request: Request) -> StreamingResponse:
        url = self._resolve_rest_api_url(endpoint)
        return await self._request_streaming(url, request=request)

    def _resolve_rest_api_url(self, endpoint: str) -> str:
        endpoint = endpoint.removeprefix("/")
        return f"{self.rest_url}/{endpoint}"

    async def _graphql(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | str | None:
        return await self._request(
            url=self.graphql_url,
            media_type="json",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"query": query, "variables": variables}),
        )

    async def _request(
        self,
        url: str,
        media_type: str = "json",
        **params: Any,
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
                ";",
            )
            if content_disposition:
                filename_set = False
                for i, e in enumerate(content_disposition):
                    cd = e.strip()
                    if cd.startswith("filename=") and filename:
                        content_disposition[i] = f'filename="{filename}"'
                        filename_set = True
                    if cd.startswith("filename*=UTF-8''") and filename:
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

    async def _rest_iterate(self, url: str, per_page: int = 100) -> list[Any]:
        logger.debug(f"Request iterate {url}")

        params = {
            "per_page": per_page,
            "pagination": "keyset",
            "order_by": "id",
            "sort": "asc",
        }

        items = []
        _url: str | None = url_add_query_params(url, params)
        while _url:
            response = await self._send_request(_url)

            content = await response.json()
            if not isinstance(content, list):
                raise HTTPException(
                    status_code=422,
                    detail="Unexpected: requested API do not return a list",
                )
            items.extend(content)

            links = self._get_links_from_headers(response)
            _url = links.get("next") if len(content) == per_page else None

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
        method: str | HttpMethod = HttpMethod.GET,
        headers: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        body: str | bytes | dict | None = None,
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
            detail = (
                f"HTTP {response.status} "
                f"| {method} {response.url}"
                f": {await response.text()}"
            )
            raise HTTPException(
                status_code=response.status,
                detail=detail,
            )

        return response


@no_type_check
def _adapt_graphql_project_reference(
    project_data: GitlabGraphQL_ProjectReference,
) -> ProjectReference:
    return ProjectReference(
        id=int(project_data["id"].split("/")[-1]),
        name=project_data["name"],
        path=project_data["fullPath"],
        topics=project_data["topics"],
        categories=get_categories_from_topics(project_data["topics"]),
    )


@no_type_check
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
        categories=get_categories_from_topics(project_data["topics"]),
        created_at=project_data["createdAt"],
        last_update=project_data["lastActivityAt"],
        star_count=project_data["starCount"],
        default_branch=project_data["repository"]["rootRef"],
        readme=readme,
        metadata=metadata,
        extent=extent,
    )


@no_type_check
def _adapt_graphql_project(project_data: GitlabGraphQL_Project) -> Project:
    readme, metadata = _process_readme_and_metadata(project_data, save=False)
    extent = _process_spatial_extent(project_data, save=False)
    categories = get_categories_from_topics(project_data["topics"])

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

    _mlflow = (
        MLflow(
            tracking_uri=f"{clean_url(MLFLOW_URL)}{project_data['fullPath']}/tracking/",
            registered_models=[],
        )
        if MLFLOW_URL
        and any(c.features.get("mlflow") == FeatureVal.ENABLE for c in categories)
        else None
    )

    gitlab_access_level = project_data["maxAccessLevel"]["integerValue"]
    if gitlab_access_level >= MAINTAINER_ACCESS_LEVEL:
        access_level = AccessLevel.ADMINISTRATOR
    elif gitlab_access_level >= DEVELOPER_ACCESS_LEVEL:
        access_level = AccessLevel.CONTRIBUTOR
    elif gitlab_access_level >= GUEST_ACCESS_LEVEL:
        access_level = AccessLevel.VISITOR
    else:
        access_level = AccessLevel.NO_ACCESS

    return Project(
        id=int(project_data["id"].split("/")[-1]),
        name=project_data["name"],
        full_name=project_data["nameWithNamespace"],
        path=project_data["fullPath"],
        description=project_data["description"],
        topics=project_data["topics"],
        url=project_data["webUrl"],
        bug_tracker=project_data["webUrl"] + "/issues",
        categories=categories,
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
        mlflow=_mlflow,
        access_level=access_level,
    )


def _process_readme_and_metadata(
    project_data: GitlabGraphQL_ProjectPreview,
    save: bool = True,
) -> tuple[str, dict]:
    if all(e in project_data for e in ["_readme", "_metadata"]):
        readme, metadata = project_data["_readme"], project_data["_metadata"]
    elif project_data["repository"]["readme"]["nodes"]:
        readme, metadata = md.parse(
            project_data["repository"]["readme"]["nodes"][0]["rawBlob"],
        )
        if save:
            project_data["_readme"] = readme
            project_data["_metadata"] = metadata
    else:
        readme, metadata = "", {}

    if project_data["repository"]["preview"]["nodes"]:
        preview_path = project_data["repository"]["preview"]["nodes"][0]["path"]
        metadata.setdefault("preview", preview_path)

    return readme, metadata


def _process_spatial_extent(
    project_data: GitlabGraphQL_ProjectPreview,
    save: bool = True,
) -> BaseGeometry | None:
    if "_extent" in project_data:
        return project_data["_extent"]

    _, metadata = _process_readme_and_metadata(project_data, save=save)
    if extent_src := metadata.get("extent", {}).get("spatial"):
        if isinstance(extent_src, list) and len(extent_src) == BBOX_LEN:
            extent = geo.bbox2geom(extent_src)
        elif isinstance(extent_src, str):
            extent = geo.wkt2geom(extent_src)
        else:
            extent = None

        if extent and save:
            project_data["_extent"] = extent
        return extent
    return None
