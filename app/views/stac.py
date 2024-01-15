import asyncio
import logging
import time
from collections import namedtuple

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient, GitlabProject
from app.api.stac import (
    Category,
    CategoryFromCollectionIdDep,
    STACSearchQuery,
    build_features_collection,
    build_stac_collection,
    build_stac_collections,
    build_stac_item,
    build_stac_item_preview,
    build_stac_root,
    get_categories,
    get_project_category,
    paginate_projects,
    search_projects,
)
from app.config import (
    ENABLE_CACHE,
    GITLAB_URL,
    STAC_CATEGORIES,
    STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
    STAC_PROJECTS_ASSETS_RULES,
    STAC_PROJECTS_CACHE_TIMEOUT,
    STAC_ROOT_CONF,
    STAC_SEARCH_CACHE_TIMEOUT,
)
from app.dependencies import GitlabTokenDep

logger = logging.getLogger("app")

router = APIRouter()


PROJECT_CACHE = {}
SEARCH_CACHE = {"readme": {}}

CachedProjectSTAC = namedtuple("CachedProjectSTAC", ["time", "last_activity", "stac"])


CONFORMANCE = [
    "https://api.stacspec.org/v1.0.0/core",
    "https://api.stacspec.org/v1.0.0/collections",
    "https://api.stacspec.org/v1.0.0/ogcapi-features",
    "https://api.stacspec.org/v1.0.0-rc.1/ogcapi-features#free-text",
    "https://api.stacspec.org/v1.0.0/item-search",
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
        categories=[*STAC_CATEGORIES],
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
    page: int = 1,
    q: str = "",
    limit: int = STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    bbox: str = "",
    datetime: str = "",
):
    search_query = STACSearchQuery(
        limit=limit,
        bbox=[float(p) for p in bbox.split(",")] if bbox else [],
        datetime=datetime if datetime else None,
        collections=[category["id"]],
        q=q.split(",") if q else [],
    )
    return await _stac_search(
        request=request,
        token=token,
        route="stac2_collection_items",
        search_query=search_query,
        category=category,
        page=page,
    )


@router.get("/collections/{collection_id}/items/{feature_id:path}")
async def stac2_collection_feature(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryFromCollectionIdDep,
    feature_id: str,
):
    cache_key = feature_id
    if (
        cache_key in PROJECT_CACHE
        and time.time() - PROJECT_CACHE[cache_key].time < STAC_PROJECTS_CACHE_TIMEOUT
    ):
        return PROJECT_CACHE[cache_key].stac

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    project = await gitlab_client.get_project(project_id=feature_id)

    if category["gitlab_topic"] not in project["topics"]:
        raise HTTPException(
            status_code=400,
            detail=f"Project '{feature_id}' do not belong to topic '{category['gitlab_topic']}'",
        )

    if (
        cache_key in PROJECT_CACHE
        and PROJECT_CACHE[cache_key].last_activity == project["last_activity_at"]
    ):
        stac = PROJECT_CACHE[cache_key].stac
        PROJECT_CACHE[cache_key] = CachedProjectSTAC(
            time=time.time(),
            last_activity=project["last_activity_at"],
            stac=stac,
        )
        return stac

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
            category=category,
            request=request,
            token=token,
        )
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if ENABLE_CACHE:
        PROJECT_CACHE[cache_key] = CachedProjectSTAC(
            time=time.time(),
            last_activity=project["last_activity_at"],
            stac=project_stac,
        )

    return project_stac


@router.get("/search")
async def stac2_search(
    request: Request,
    token: GitlabTokenDep,
    page: int = 1,
    q: str = "",
    limit: int = STAC_CATEGORIES_PAGE_DEFAULT_SIZE,
    bbox: str = "",
    datetime: str = "",
    intersects: str = "null",
    ids: str = "",
    collections: str = "",
):
    search_query = STACSearchQuery(
        limit=limit,
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
        page=page,
    )


async def _stac_search(
    request: Request,
    token: GitlabTokenDep,
    route: str,
    search_query: STACSearchQuery,
    category: Category | None,
    page: int = 1,
) -> dict:
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    projects = await search_projects(search_query, client=gitlab_client)
    page_projects, pagination = paginate_projects(
        projects, page, per_page=search_query.limit
    )

    page_projects_readme = await asyncio.gather(
        *(get_cached_readme(gitlab_client, p) for p in page_projects)
    )

    return build_features_collection(
        features=[
            build_stac_item_preview(
                project=p,
                readme=page_projects_readme[i],
                category=get_project_category(p),
                request=request,
                token=token,
            )
            for i, p in enumerate(page_projects)
        ],
        pagination=pagination,
        route=route,
        category=category,
        request=request,
        token=token,
    )


async def get_cached_readme(client: GitlabClient, project: GitlabProject) -> str:
    cache_key = project["id"]

    if (
        cache_key in SEARCH_CACHE["readme"]
        and time.time() - SEARCH_CACHE["readme"][cache_key]["time"]
        < STAC_SEARCH_CACHE_TIMEOUT
    ):
        return SEARCH_CACHE["readme"][cache_key]["content"]

    readme = await client.get_readme(project)

    if ENABLE_CACHE:
        SEARCH_CACHE["readme"][cache_key] = {
            "time": time.time(),
            "content": readme,
        }
    return readme
