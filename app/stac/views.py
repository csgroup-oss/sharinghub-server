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

import asyncio
import json
import logging
import time

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter

from app.auth import GitlabTokenDep
from app.providers.client import CursorPagination, GitlabClient
from app.providers.schemas import Project
from app.settings import ENABLE_CACHE, GITLAB_URL
from app.stac.api.category import (
    Category,
    CategoryFromCollectionIdDep,
    get_categories,
    get_category,
)
from app.utils import geo
from app.utils.cache import cache

from .api.build import (
    build_features_collection,
    build_stac_collection,
    build_stac_collections,
    build_stac_item,
    build_stac_item_preview,
    build_stac_item_reference,
    build_stac_root,
)
from .api.search import (
    SearchMode,
    STACPagination,
    STACSearchQuery,
    get_state_query,
    parse_stac_query,
)
from .settings import (
    STAC_PROJECTS_CACHE_TIMEOUT,
    STAC_ROOT_CONF,
    STAC_SEARCH_PAGE_DEFAULT_SIZE,
)

logger = logging.getLogger("app")

router = APIRouter()


CONFORMANCE = [
    "https://api.stacspec.org/v1.0.0/core",
    "https://api.stacspec.org/v1.0.0/collections",
    "https://api.stacspec.org/v1.0.0/ogcapi-features",
    "https://api.stacspec.org/v1.0.0/ogcapi-features#sort",
    "https://api.stacspec.org/v1.0.0-rc.1/ogcapi-features#free-text",
    "https://api.stacspec.org/v1.0.0/item-search",
    "https://api.stacspec.org/v1.0.0/item-search#sort",
    "https://api.stacspec.org/v1.0.0-rc.1/item-search#free-text",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
]


@router.get("")
@router.get("/")
async def stac_root(request: Request, token: GitlabTokenDep) -> dict:
    return build_stac_root(
        root_config=STAC_ROOT_CONF,
        conformance_classes=CONFORMANCE,
        categories=get_categories(),
        request=request,
        token=token,
    )


@router.get("/conformance")
async def stac_conformance() -> dict:
    return {"conformsTo": CONFORMANCE}


@router.get("/collections")
async def stac_collections(request: Request, token: GitlabTokenDep) -> dict:
    return build_stac_collections(
        categories=get_categories(),
        request=request,
        token=token,
    )


@router.get("/collections/{collection_id}")
async def stac_collection(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
) -> dict:
    return build_stac_collection(
        category=category,
        request=request,
        token=token,
    )


@router.get("/collections/{collection_id}/items")
async def stac_collection_items(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    mode: SearchMode = "full",
    before: str | None = None,
    after: str | None = None,
    limit: int = STAC_SEARCH_PAGE_DEFAULT_SIZE,
    bbox: str = "",
    datetime: str = "",
) -> dict:
    search_query = STACSearchQuery(
        limit=limit,
        bbox=[float(p) for p in bbox.split(",")] if bbox else [],
        datetime=datetime if datetime else None,
        collections=[category.id],
    )
    return await _stac_search(
        request=request,
        token=token,
        route="stac_collection_items",
        mode=mode,
        search_query=search_query,
        category=category,
        before=before,
        after=after,
    )


@router.get("/collections/{collection_id}/items/{feature_id:path}")
async def stac_collection_feature(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    feature_id: str,
) -> dict:
    if not feature_id:
        raise HTTPException(status_code=400, detail="No feature ID given")

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    project = await gitlab_client.get_project(path=feature_id)
    user: str | None = await cache.get(token.value)
    if not user:
        user = await gitlab_client.get_user()
        await cache.set(token.value, user)

    if category != project.category:
        raise HTTPException(
            status_code=400,
            detail=f"Category mismatch for project '{project.path}', "
            f"asked '{category.id}' but got '{project.category.id}' instead",
        )

    cache_key = ("stac", user, project.path)
    if cached_stac := await cache.get(cache_key, namespace="project"):
        elapsed_time = time.time() - cached_stac["time"]
        if elapsed_time < STAC_PROJECTS_CACHE_TIMEOUT:
            logger.debug(
                f"Read project stac from cache '{project.path}' "
                f"({elapsed_time:.3f}/{STAC_PROJECTS_CACHE_TIMEOUT} s)",
            )
            return cached_stac["stac"]
        if cached_stac["checksum"] == _get_project_checksum(project):
            logger.debug(
                "Read project stac from cache"
                f"'{project.path}' (no changes detected)",
            )
            cached_stac["time"] = time.time()
            await cache.set(cache_key, cached_stac, namespace="project")
            return cached_stac["stac"]

    await _resolve_license(project, gitlab_client)

    project_stac = build_stac_item(
        project=project,
        request=request,
        token=token,
    )
    if ENABLE_CACHE:
        logger.debug(f"Write stac '{feature_id}' in cache")
        cached_stac = {
            "time": time.time(),
            "checksum": _get_project_checksum(project),
            "stac": project_stac,
        }
        await cache.set(cache_key, cached_stac, namespace="project")

    return project_stac


def _get_project_checksum(project: Project) -> int:
    return hash((project.last_commit, project.last_update, *project.topics))


@router.get("/search")
async def stac_search_get(
    request: Request,
    token: GitlabTokenDep,
    before: str | None = None,
    after: str | None = None,
    limit: int = STAC_SEARCH_PAGE_DEFAULT_SIZE,
    sortby: str | None = None,
    q: str = "",
    bbox: str = "",
    datetime: str = "",
    intersects: str = "null",
    ids: str = "",
    collections: str = "",
    mode: SearchMode = "full",
) -> dict:
    search_query = STACSearchQuery(
        limit=limit,
        sortby=sortby,
        bbox=[float(p) for p in bbox.split(",")] if bbox else [],
        datetime=datetime if datetime else None,
        intersects=json.loads(intersects),
        ids=ids.split(",") if ids else [],
        collections=collections.split(",") if collections else [],
        q=q.split(",") if q else [],
    )
    return await _stac_search(
        request=request,
        token=token,
        route="stac_search_get",
        mode=mode,
        search_query=search_query,
        category=None,
        before=before,
        after=after,
    )


@router.post("/search")
async def stac_search_post(
    request: Request,
    token: GitlabTokenDep,
    search_query: STACSearchQuery,
    before: str | None = None,
    after: str | None = None,
    mode: SearchMode = "full",
) -> dict:
    return await _stac_search(
        request=request,
        token=token,
        route="stac_search_get",
        mode=mode,
        search_query=search_query,
        category=None,
        before=before,
        after=after,
    )


async def _stac_search(  # noqa: C901
    request: Request,
    token: GitlabTokenDep,
    route: str,
    mode: SearchMode,
    search_query: STACSearchQuery,
    category: Category | None,
    before: str | None,
    after: str | None,
) -> dict:
    count_collections = len(search_query.collections)
    if count_collections > 1:
        raise HTTPException(
            status_code=422,
            detail="Search is enabled only for one collection, "
            f"got {count_collections} collections",
        )
    if count_collections == 0:
        return build_features_collection(
            features=[],
            state_query={},
            pagination=STACPagination(
                limit=search_query.limit,
                matched=0,
                returned=0,
                prev=None,
                next=None,
            ),
            route=route,
            category=None,
            request=request,
            token=token,
        )

    category = category if category else get_category(search_query.collections[0])

    if not category:
        raise HTTPException(
            status_code=422,
            detail=f"Category not found for: {', '.join(search_query.collections)}",
        )

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)

    query, topics, flags = parse_stac_query(" ".join(search_query.q))
    topics.append(category.gitlab_topic)

    if _sortby := search_query.sortby:
        if isinstance(_sortby, str):
            sort_direction = "desc" if _sortby.startswith("-") else "asc"
            sort_field = _sortby.lstrip("-+").strip()
            sort_field = sort_field.replace("properties.", "")
            sort_field = sort_field.replace("sharinghub:", "")
            sortby = sort_field, sort_direction
        elif len(_sortby) > 0:
            sortby = _sortby[0]["field"], _sortby[0]["direction"]
        else:
            sortby = None
    else:
        sortby = None

    if search_query.intersects:
        extent = geo.geojson2geom(search_query.intersects)
        if not extent:
            raise HTTPException(
                status_code=422,
                detail=f"Could not process 'intersects': {search_query.intersects}",
            )
    elif search_query.bbox:
        extent = geo.bbox2geom(search_query.bbox)
        if not extent:
            raise HTTPException(
                status_code=422,
                detail=f"Could not process 'bbox': {search_query.bbox}",
            )
    else:
        extent = None

    match mode:
        case "reference":
            projects_refs, _pagination = await gitlab_client.search_references(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                limit=search_query.limit,
                sort=sortby,
                start=after,
                end=before,
            )
            count = len(projects_refs)
            features = [
                build_stac_item_reference(p, request=request, token=token)
                for p in projects_refs
            ]
        case "preview":
            projects_prevs, _pagination = await gitlab_client.search_previews(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                extent=extent,
                datetime_range=search_query.datetime_range,
                limit=search_query.limit,
                sort=sortby,
                start=after,
                end=before,
            )
            count = len(projects_prevs)
            features = [
                build_stac_item_preview(p, request=request, token=token)
                for p in projects_prevs
            ]
        case "full":
            projects, _pagination = await gitlab_client.search(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                extent=extent,
                datetime_range=search_query.datetime_range,
                limit=search_query.limit,
                sort=sortby,
                start=after,
                end=before,
            )
            count = len(projects)
            await asyncio.gather(
                *(_resolve_license(p, gitlab_client) for p in projects),
            )
            features = [
                build_stac_item(p, request=request, token=token) for p in projects
            ]
    pagination = _create_stac_pagination(
        _pagination,
        limit=search_query.limit,
        count=count,
    )
    return build_features_collection(
        features=features,
        state_query=get_state_query(
            search_query,
            exclude=["collections"] if route == "stac_collection_items" else None,
        ),
        pagination=pagination,
        route=route,
        category=category,
        request=request,
        token=token,
    )


def _create_stac_pagination(
    cursor_pagination: CursorPagination,
    limit: int,
    count: int,
) -> STACPagination:
    return STACPagination(
        limit=limit,
        matched=cursor_pagination["total"],
        returned=count,
        prev=cursor_pagination["start"],
        next=cursor_pagination["end"],
    )


async def _resolve_license(project: Project, client: GitlabClient) -> None:
    cache_key = project.path
    nolicense = 1

    license_ = await cache.get(cache_key, namespace="license")
    if not license_:
        license_ = await client.get_license(project)
        await cache.set(
            cache_key,
            license_ if license_ else nolicense,
            namespace="license",
            ttl=int(STAC_PROJECTS_CACHE_TIMEOUT),
        )

    if license_ and license_ != nolicense:
        project.license = license_
