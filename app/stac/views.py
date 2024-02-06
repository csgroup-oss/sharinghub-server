import asyncio
import logging
import time

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter

from app.auth import GitlabTokenDep
from app.providers.client import GitlabClient
from app.providers.schemas import Project
from app.settings import ENABLE_CACHE, GITLAB_URL
from app.stac.api.category import Category, CategoryFromCollectionIdDep, get_categories
from app.utils.cache import cache

from .api.build import (
    STACSearchQuery,
    build_features_collection,
    build_stac_collection,
    build_stac_collections,
    build_stac_item,
    build_stac_item_preview,
    build_stac_root,
)
from .api.search import search_projects
from .settings import (
    STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
    STAC_PROJECTS_ASSETS_RULES,
    STAC_PROJECTS_CACHE_TIMEOUT,
    STAC_ROOT_CONF,
    STAC_SEARCH_CACHE_TIMEOUT,
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


@router.get("/")
async def stac2_root(request: Request, token: GitlabTokenDep):
    return build_stac_root(
        root_config=STAC_ROOT_CONF,
        conformance_classes=CONFORMANCE,
        categories=get_categories(),
        request=request,
        token=token,
    )


@router.get("/conformance")
async def stac2_conformance():
    return {"conformsTo": CONFORMANCE}


@router.get("/collections")
async def stac2_collections(request: Request, token: GitlabTokenDep):
    return build_stac_collections(
        categories=get_categories(), request=request, token=token
    )


@router.get("/collections/{collection_id}")
async def stac2_collection(
    request: Request, token: GitlabTokenDep, category: CategoryFromCollectionIdDep
):
    return build_stac_collection(
        category=category,
        request=request,
        token=token,
    )


@router.get("/collections/{collection_id}/items")
async def stac2_collection_items(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    limit: int = STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    sortby: str | None = None,
    prev: str | None = None,
    next: str | None = None,
    q: str = "",
    bbox: str = "",
    datetime: str = "",
):
    search_query = STACSearchQuery(
        limit=limit,
        sortby=sortby,
        bbox=[float(p) for p in bbox.split(",")] if bbox else [],
        datetime=datetime if datetime else None,
        collections=[category.id],
        q=q.split(",") if q else [],
    )
    return await _stac_search(
        request=request,
        token=token,
        route="stac2_collection_items",
        search_query=search_query,
        category=category,
        prev=prev,
        next=next,
    )


@router.get("/collections/{collection_id}/items/{feature_id:path}")
async def stac2_collection_feature(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    feature_id: str,
):
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    project = await gitlab_client.get_project(path=feature_id)

    if not project.category:
        raise HTTPException(
            status_code=400, detail=f"Category not found for project '{project.path}'"
        )
    elif category != project.category:
        raise HTTPException(
            status_code=400,
            detail=f"Category mismatch for project '{project.path}', "
            f"asked '{category.id}' but got '{project.category.id}' instead",
        )

    cache_key = project.path
    cache_val = await cache.get(cache_key, namespace="project")
    if cache_val:
        elapsed_time = time.time() - cache_val["time"]
        if elapsed_time < STAC_PROJECTS_CACHE_TIMEOUT:
            logger.debug(
                f"Read project stac from cache '{project.path}' "
                f"({elapsed_time:.3f}/{STAC_PROJECTS_CACHE_TIMEOUT} s)"
            )
            return cache_val["stac"]
        elif cache_val["last_activity"] == project.last_update and set(
            cache_val["topics"]
        ) == set(project.topics):
            logger.debug(
                "Read project stac from cache" f"'{project.path}' (no changes detected)"
            )
            cache_val["time"] = time.time()
            await cache.set(cache_key, cache_val, namespace="project")
            return cache_val["stac"]

    readme, files, release = await asyncio.gather(
        gitlab_client.get_readme(project),
        gitlab_client.get_files(project),
        gitlab_client.get_latest_release(project),
    )

    try:
        project_stac = build_stac_item(
            project=project,
            readme=readme,
            files=files,
            assets_rules=STAC_PROJECTS_ASSETS_RULES,
            release=release,
            release_source_format=STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
            request=request,
            token=token,
        )
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if ENABLE_CACHE:
        logger.debug(f"Write stac '{feature_id}' in cache")
        cache_val = {
            "time": time.time(),
            "last_activity": project.last_update,
            "topics": project.topics,
            "stac": project_stac,
        }
        await cache.set(cache_key, cache_val, namespace="project")

    return project_stac


@router.get("/search")
async def stac2_search(
    request: Request,
    token: GitlabTokenDep,
    limit: int = STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    sortby: str | None = None,
    prev: str | None = None,
    next: str | None = None,
    q: str = "",
    bbox: str = "",
    datetime: str = "",
    intersects: str = "null",
    ids: str = "",
    collections: str = "",
):
    search_query = STACSearchQuery(
        limit=limit,
        sortby=sortby,
        bbox=[float(p) for p in bbox.split(",")] if bbox else [],
        datetime=datetime if datetime else None,
        intersects=intersects,
        ids=ids.split(",") if ids else [],
        collections=collections.split(",") if collections else [],
        q=q.split(",") if q else [],
    )
    return await _stac_search(
        request=request,
        token=token,
        route="stac2_search",
        search_query=search_query,
        category=None,
        prev=prev,
        next=next,
    )


async def _stac_search(
    request: Request,
    token: GitlabTokenDep,
    route: str,
    search_query: STACSearchQuery,
    category: Category | None,
    prev: str | None,
    next: str | None,
) -> dict:
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    projects, pagination = await search_projects(
        gitlab_client, search_query, category, prev=prev, next=next
    )
    projects_readme = await asyncio.gather(
        *(get_cached_readme(gitlab_client, p) for p in projects)
    )
    return build_features_collection(
        features=[
            build_stac_item_preview(
                project=p,
                readme=projects_readme[i],
                request=request,
                token=token,
            )
            for i, p in enumerate(projects)
        ],
        pagination=pagination,
        route=route,
        category=category,
        request=request,
        token=token,
    )


async def get_cached_readme(client: GitlabClient, project: Project) -> str:
    cache_key = project.path

    cached_val = await cache.get(project.path, namespace="readme")
    if cached_val and time.time() - cached_val["time"] < STAC_SEARCH_CACHE_TIMEOUT:
        logger.debug(f"Read readme from cache for '{project.path}'")
        return cached_val["content"]

    readme = await client.get_readme(project)
    if ENABLE_CACHE:
        logger.debug(f"Write readme in cache for '{project.path}'")
        cached_val = {"time": time.time(), "content": readme}
        await cache.set(cache_key, cached_val, namespace="readme")
    return readme
