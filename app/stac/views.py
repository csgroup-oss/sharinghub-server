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


@router.get("/")
async def stac_root(request: Request, token: GitlabTokenDep):
    return build_stac_root(
        root_config=STAC_ROOT_CONF,
        conformance_classes=CONFORMANCE,
        categories=get_categories(),
        request=request,
        token=token,
    )


@router.get("/conformance")
async def stac_conformance():
    return {"conformsTo": CONFORMANCE}


@router.get("/collections")
async def stac_collections(request: Request, token: GitlabTokenDep):
    return build_stac_collections(
        categories=get_categories(), request=request, token=token
    )


@router.get("/collections/{collection_id}")
async def stac_collection(
    request: Request, token: GitlabTokenDep, category: CategoryFromCollectionIdDep
):
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
    prev: str | None = None,
    next: str | None = None,
    limit: int = STAC_SEARCH_PAGE_DEFAULT_SIZE,
    bbox: str = "",
    datetime: str = "",
):
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
        prev=prev,
        next=next,
    )


@router.get("/collections/{collection_id}/items/{feature_id:path}")
async def stac_collection_feature(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    feature_id: str,
):
    if not feature_id:
        raise HTTPException(status_code=400, detail=f"No feature ID given")

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
        elif cache_val["checksum"] == _get_project_checksum(project):
            logger.debug(
                "Read project stac from cache" f"'{project.path}' (no changes detected)"
            )
            cache_val["time"] = time.time()
            await cache.set(cache_key, cache_val, namespace="project")
            return cache_val["stac"]

    if license := await gitlab_client.get_license(project):
        project.license = license

    try:
        project_stac = build_stac_item(
            project=project,
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
            "checksum": _get_project_checksum(project),
            "stac": project_stac,
        }
        await cache.set(cache_key, cache_val, namespace="project")

    return project_stac


def _get_project_checksum(project: Project) -> int:
    return hash((project.last_commit, project.last_update, *project.topics))


@router.get("/search")
async def stac_search(
    request: Request,
    token: GitlabTokenDep,
    prev: str | None = None,
    next: str | None = None,
    limit: int = STAC_SEARCH_PAGE_DEFAULT_SIZE,
    sortby: str | None = None,
    q: str = "",
    bbox: str = "",
    datetime: str = "",
    intersects: str = "null",
    ids: str = "",
    collections: str = "",
    mode: SearchMode = "full",
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
        route="stac_search",
        mode=mode,
        search_query=search_query,
        category=None,
        prev=prev,
        next=next,
    )


@router.post("/search")
async def stac_search(
    request: Request,
    token: GitlabTokenDep,
    search_query: STACSearchQuery,
    prev: str | None = None,
    next: str | None = None,
    mode: SearchMode = "full",
):
    return await _stac_search(
        request=request,
        token=token,
        route="stac_search",
        mode=mode,
        search_query=search_query,
        category=None,
        prev=prev,
        next=next,
    )


async def _stac_search(
    request: Request,
    token: GitlabTokenDep,
    route: str,
    mode: SearchMode,
    search_query: STACSearchQuery,
    category: Category | None,
    prev: str | None,
    next: str | None,
) -> dict:
    if len(search_query.collections) != 1:
        raise HTTPException(
            status_code=422,
            detail="Search is enabled only for one collection exactly, "
            f"got {len(search_query.collections)} collections",
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

    sortby = search_query.sortby
    if sortby:
        sortby = sortby.replace("properties.", "")
        sortby = sortby.replace("sharinghub:", "")

    match mode:
        case "reference":
            projects, _pagination = await gitlab_client.search_references(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                limit=search_query.limit,
                sort=sortby,
                prev=prev,
                next=next,
            )
            features = [
                build_stac_item_reference(p, request=request, token=token)
                for p in projects
            ]
        case "preview":
            projects, _pagination = await gitlab_client.search_previews(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                bbox=search_query.bbox,
                datetime_range=search_query.datetime_range,
                limit=search_query.limit,
                sort=sortby,
                prev=prev,
                next=next,
            )
            features = [
                build_stac_item_preview(p, request=request, token=token)
                for p in projects
            ]
        case "full":
            projects, _pagination = await gitlab_client.search(
                ids=search_query.ids,
                query=query,
                topics=topics,
                flags=flags,
                bbox=search_query.bbox,
                datetime_range=search_query.datetime_range,
                limit=search_query.limit,
                sort=sortby,
                prev=prev,
                next=next,
            )
            features = [
                build_stac_item(p, request=request, token=token) for p in projects
            ]
    pagination = _create_stac_pagination(
        _pagination, limit=search_query.limit, count=len(projects)
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
    cursor_pagination: CursorPagination, limit: int, count: int
) -> STACPagination:
    return STACPagination(
        limit=limit,
        matched=cursor_pagination["total"],
        returned=count,
        prev=cursor_pagination["start"],
        next=cursor_pagination["end"],
    )
