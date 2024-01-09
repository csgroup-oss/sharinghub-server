import asyncio
import enum
import logging
import time
from collections import namedtuple
from datetime import datetime as dt
from typing import Annotated

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import (
    BaseModel,
    Field,
    Json,
    SerializationInfo,
    computed_field,
    field_serializer,
    field_validator,
)

from app.api.gitlab import GitlabClient, GitlabProject
from app.api.stac import (
    build_stac_category,
    build_stac_for_project,
    build_stac_root,
    build_stac_search_result,
)
from app.config import (
    ENABLE_CACHE,
    GITLAB_URL,
    STAC_CATEGORIES,
    STAC_CATEGORIES_CACHE_TIMEOUT,
    STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT,
    STAC_PROJECTS_ASSETS_RULES,
    STAC_PROJECTS_CACHE_TIMEOUT,
)
from app.dependencies import GitlabTokenDep
from app.utils.geo import find_parent_of_hashes, hash_polygon

logger = logging.getLogger("app")

CATEGORIES_CACHE = {}
PROJECT_CACHE = {}

CategoryName = enum.StrEnum("CategoryName", {k: k for k in STAC_CATEGORIES})
CachedCategorySTAC = namedtuple("CachedCategorySTAC", ["time", "stac"])
CachedProjectSTAC = namedtuple("CachedProjectSTAC", ["time", "last_activity", "stac"])

router = APIRouter()


class STACSearchForm(BaseModel):
    limit: Annotated[int, Field(strict=True, gt=0)] = 10
    bbox: list[float] = Field(default_factory=list)
    datetime: str = ""
    intersects: Json = Field(default=None)
    ids: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    q: list[str] = Field(default_factory=list)

    @field_validator("datetime")
    @classmethod
    def validate_datetime(cls, d: str) -> str:
        if d:
            d1, *do = d.split("/")
            dt.fromisoformat(d1)
            if do:
                d2 = do[0]
                dt.fromisoformat(d2)
        return d

    @computed_field
    def datetime_range(self) -> tuple[dt, dt] | None:
        if self.datetime:
            start_dt_str, *other_dts_str = self.datetime.split("/")
            start_dt = dt.fromisoformat(start_dt_str)
            if other_dts_str:
                end_dt_str = other_dts_str[0]
                end_dt = dt.fromisoformat(end_dt_str)
            else:
                end_dt = start_dt
            return start_dt, end_dt
        return None

    @field_serializer("bbox", "ids", "collections", "q", when_used="unless-none")
    def serialize_lists(self, v: list[str | float], _info: SerializationInfo) -> str:
        return ",".join(str(e) for e in v)


@router.post("/search")
async def stac_search_post(
    request: Request,
    token: GitlabTokenDep,
    search_form: STACSearchForm,
    page: int = 1,
):
    return await _stac_search(
        request=request,
        token=token,
        search_form=search_form,
        page=page,
    )


@router.get("/search")
async def stac_search(
    request: Request,
    token: GitlabTokenDep,
    page: int = 1,
    limit: int = 10,
    bbox: str = "",
    datetime: str = "",
    intersects: str = "null",
    ids: str = "",
    collections: str = "",
    q: str = "",
):
    try:
        search_form = STACSearchForm(
            limit=limit,
            bbox=[float(p) for p in bbox.split(",")] if bbox else [],
            datetime=datetime,
            intersects=intersects,
            ids=ids.split(",") if ids else [],
            collections=collections.split(",") if collections else [],
            q=q.split(",") if q else [],
        )
        return await _stac_search(
            request=request,
            token=token,
            search_form=search_form,
            page=page,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))


async def _stac_search(
    request: Request,
    token: GitlabTokenDep,
    search_form: STACSearchForm,
    page: int = 1,
):
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)

    categories = search_form.collections
    if any(c not in STAC_CATEGORIES for c in categories):
        raise HTTPException(
            status_code=422,
            detail=f"Collections should be one of: {', '.join(STAC_CATEGORIES)}",
        )
    if not categories:
        categories = list(STAC_CATEGORIES)

    search_extent: dict[str, GitlabProject] = {}
    if search_form.bbox:
        bbox_geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [search_form.bbox[0], search_form.bbox[1]],
                    [search_form.bbox[2], search_form.bbox[1]],
                    [search_form.bbox[2], search_form.bbox[3]],
                    [search_form.bbox[0], search_form.bbox[3]],
                    [search_form.bbox[0], search_form.bbox[1]],
                ]
            ],
        }
        cells = hash_polygon(bbox_geojson)
        search_extent_queries = [" ".join(cells)]
        try:
            while True:
                cells = find_parent_of_hashes(cells)
                search_extent_queries.append(" ".join(cells))
        except:
            pass
        for query in search_extent_queries:
            gitlab_search = await gitlab_client.search(scope="projects", query=query)
            gitlab_search = [
                project
                for project in gitlab_search
                if any(
                    STAC_CATEGORIES[c]["gitlab_topic"] in project["topics"]
                    for c in categories
                )
            ]
            for p in gitlab_search:
                search_extent[p["id"]] = p

    search_query: dict[str, GitlabProject] = {}
    if search_form.q:
        for query in search_form.q:
            gitlab_search = await gitlab_client.search(scope="projects", query=query)
            gitlab_search = [
                project
                for project in gitlab_search
                if any(
                    STAC_CATEGORIES[c]["gitlab_topic"] in project["topics"]
                    for c in categories
                )
            ]
            for p in gitlab_search:
                search_query[p["id"]] = p

    if search_form.bbox and search_form.q:
        _intersect_ids = search_extent.keys() & search_query.keys()
        projects = [
            p
            for p in (search_extent | search_query).values()
            if p["id"] in _intersect_ids
        ]
    else:
        projects = list((search_extent | search_query).values())

    features = []
    for project in projects:
        _category = None
        for c in STAC_CATEGORIES:
            if STAC_CATEGORIES[c]["gitlab_topic"] in project["topics"]:
                _category = {"name": c, **STAC_CATEGORIES[c]}

        readme, files, release = await asyncio.gather(
            gitlab_client.get_readme(project),
            gitlab_client.get_files(project),
            gitlab_client.get_latest_release(project),
        )

        try:
            _feature = build_stac_for_project(
                category=_category,
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

        features.append(_feature)

    if search_form.ids:
        features = [f for f in features if f["id"] in search_form.ids]

    if dt_range := search_form.datetime_range:
        search_start_dt, search_end_dt = dt_range
        _features = []
        for f in features:
            f_start_dt = dt.fromisoformat(f["properties"]["start_datetime"])
            f_end_dt = dt.fromisoformat(f["properties"]["end_datetime"])
            if search_start_dt <= f_start_dt <= f_end_dt <= search_end_dt:
                _features.append(f)
        features = _features

    search_query = search_form.model_dump(
        mode="json",
        exclude={"datetime_range"},
        exclude_defaults=True,
        exclude_none=True,
        exclude_unset=True,
    )
    return build_stac_search_result(
        features=features,
        page=page,
        limit=search_form.limit,
        search_query=search_query,
        request=request,
        token=token,
    )


@router.get("/")
async def stac_root(
    request: Request,
    token: GitlabTokenDep,
):
    return build_stac_root(
        categories=STAC_CATEGORIES,
        request=request,
        token=token,
    )


@router.get("/{category}")
async def stac_category(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryName,
):
    cache_key = (category, token.value)
    if (
        cache_key in CATEGORIES_CACHE
        and time.time() - CATEGORIES_CACHE[cache_key].time
        < STAC_CATEGORIES_CACHE_TIMEOUT
    ):
        return CATEGORIES_CACHE[cache_key].stac

    _category = {"name": category, **STAC_CATEGORIES[category]}

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    projects = await gitlab_client.get_projects(_category["gitlab_topic"])

    category_stac = build_stac_category(
        category=_category,
        projects=projects,
        request=request,
        token=token,
    )

    if ENABLE_CACHE:
        CATEGORIES_CACHE[cache_key] = CachedCategorySTAC(
            time=time.time(), stac=category_stac
        )

    return category_stac


@router.get("/{category}/{project_path:path}")
async def stac_project(
    request: Request,
    token: GitlabTokenDep,
    category: CategoryName,
    project_path: str,
):
    cache_key = project_path
    if (
        cache_key in PROJECT_CACHE
        and time.time() - PROJECT_CACHE[cache_key].time < STAC_PROJECTS_CACHE_TIMEOUT
    ):
        return PROJECT_CACHE[cache_key].stac

    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    project = await gitlab_client.get_project(project_path)

    _category = {"name": category, **STAC_CATEGORIES[category]}
    gitlab_topic = _category["gitlab_topic"]

    if gitlab_topic not in project["topics"]:
        raise HTTPException(
            status_code=400,
            detail=f"Project '{project_path}' do not belong to topic '{gitlab_topic}'",
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
        project_stac = build_stac_for_project(
            category=_category,
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
        PROJECT_CACHE[cache_key] = CachedProjectSTAC(
            time=time.time(),
            last_activity=project["last_activity_at"],
            stac=project_stac,
        )

    return project_stac
