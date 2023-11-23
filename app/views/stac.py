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
    build_stac_for_project,
    build_stac_root,
    build_stac_search_result,
    build_stac_topic,
    get_gitlab_topic,
)
from app.config import (
    ASSETS_RULES,
    CATALOG_CACHE_TIMEOUT,
    CATALOG_TOPICS,
    ENABLE_CACHE,
    PROJECT_CACHE_TIMEOUT,
    RELEASE_SOURCE_FORMAT,
)
from app.dependencies import GitlabConfigDep, GitlabTokenDep
from app.utils.geo import find_parent_of_hashes, hash_polygon

logger = logging.getLogger("app")

CATALOG_CACHE = {}
PROJECT_CACHE = {}

TopicName = enum.StrEnum("TopicName", {k: k for k in CATALOG_TOPICS})
CachedCatalog = namedtuple("CachedCatalog", ["time", "catalog"])
CachedProject = namedtuple("CachedProject", ["time", "last_activity", "stac"])

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
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    search_form: STACSearchForm,
    page: int = 1,
):
    return await _stac_search(
        request=request,
        gitlab_config=gitlab_config,
        token=token,
        search_form=search_form,
        page=page,
    )


@router.get("/search")
async def stac_search(
    request: Request,
    gitlab_config: GitlabConfigDep,
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
            gitlab_config=gitlab_config,
            token=token,
            search_form=search_form,
            page=page,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))


async def _stac_search(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    search_form: STACSearchForm,
    page: int = 1,
):
    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)

    topics = search_form.collections
    if any(t not in CATALOG_TOPICS for t in topics):
        raise HTTPException(
            status_code=422,
            detail=f"Collections should be one of: {', '.join(CATALOG_TOPICS)}",
        )
    if not topics:
        topics = list(CATALOG_TOPICS)

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
        search_form.q.append(" ".join(cells))
        try:
            while True:
                cells = find_parent_of_hashes(cells)
                search_form.q.append(" ".join(cells))
        except:
            pass

    if search_form.q:
        _gitlab_search_result: dict[str, GitlabProject] = {}
        for query in search_form.q:
            gitlab_search = await gitlab_client.search(scope="projects", query=query)
            gitlab_search = [
                project
                for project in gitlab_search
                if any(
                    CATALOG_TOPICS[t]["gitlab_name"] in project["topics"]
                    for t in topics
                )
            ]
            for p in gitlab_search:
                if p["id"] not in _gitlab_search_result:
                    _gitlab_search_result[p["id"]] = p
        projects = list(_gitlab_search_result.values())
    else:
        projects = []
        _topics = [{"name": t, **CATALOG_TOPICS[t]} for t in topics]
        _result = await asyncio.gather(
            *(gitlab_client.get_projects(get_gitlab_topic(t)) for t in _topics)
        )
        for _topic_projects in _result:
            projects.extend(_topic_projects)

    features = []
    for project in projects:
        _topic = None
        for t in CATALOG_TOPICS:
            if CATALOG_TOPICS[t]["gitlab_name"] in project["topics"]:
                _topic = {"name": t, **CATALOG_TOPICS[t]}

        readme, files, release = await asyncio.gather(
            gitlab_client.get_readme(project),
            gitlab_client.get_files(project),
            gitlab_client.get_latest_release(project),
        )

        try:
            _feature = build_stac_for_project(
                topic=_topic,
                project=project,
                readme=readme,
                files=files,
                assets_rules=ASSETS_RULES,
                release=release,
                release_source_format=RELEASE_SOURCE_FORMAT,
                request=request,
                gitlab_config=gitlab_config,
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
        gitlab_config=gitlab_config,
        token=token,
    )


@router.get("/")
async def stac_root(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
):
    return build_stac_root(
        gitlab_config=gitlab_config,
        topics=CATALOG_TOPICS,
        request=request,
        token=token,
    )


@router.get("/{topic}")
async def stac_topic(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    topic: TopicName,
):
    cache_key = (gitlab_config["path"], topic, token.value)
    if (
        cache_key in CATALOG_CACHE
        and time.time() - CATALOG_CACHE[cache_key].time < CATALOG_CACHE_TIMEOUT
    ):
        return CATALOG_CACHE[cache_key].catalog

    _topic = {"name": topic, **CATALOG_TOPICS[topic]}

    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    projects = await gitlab_client.get_projects(get_gitlab_topic(_topic))

    catalog = build_stac_topic(
        topic=_topic,
        projects=projects,
        request=request,
        gitlab_config=gitlab_config,
        token=token,
    )

    if ENABLE_CACHE:
        CATALOG_CACHE[cache_key] = CachedCatalog(time=time.time(), catalog=catalog)

    return catalog


@router.get("/{topic}/{project_path:path}")
async def stac_project(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    topic: TopicName,
    project_path: str,
):
    cache_key = (gitlab_config["path"], project_path)
    if (
        cache_key in PROJECT_CACHE
        and time.time() - PROJECT_CACHE[cache_key].time < PROJECT_CACHE_TIMEOUT
    ):
        return PROJECT_CACHE[cache_key].stac

    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    project = await gitlab_client.get_project(project_path)

    _topic = {"name": topic, **CATALOG_TOPICS[topic]}
    gitlab_topic = get_gitlab_topic(_topic)

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
        PROJECT_CACHE[cache_key] = CachedProject(
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
        stac = build_stac_for_project(
            topic=_topic,
            project=project,
            readme=readme,
            files=files,
            assets_rules=ASSETS_RULES,
            release=release,
            release_source_format=RELEASE_SOURCE_FORMAT,
            request=request,
            gitlab_config=gitlab_config,
            token=token,
        )
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if ENABLE_CACHE:
        PROJECT_CACHE[cache_key] = CachedProject(
            time=time.time(),
            last_activity=project["last_activity_at"],
            stac=stac,
        )

    return stac
