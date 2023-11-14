import asyncio
import enum
import logging
import time
from collections import namedtuple
from datetime import datetime as dt

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

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
from app.utils.http import url_for

logger = logging.getLogger("app")

CATALOG_CACHE = {}
PROJECT_CACHE = {}

TopicName = enum.StrEnum("TopicName", {k: k for k in CATALOG_TOPICS})
CachedCatalog = namedtuple("CachedCatalog", ["time", "catalog"])
CachedProject = namedtuple("CachedProject", ["time", "last_activity", "stac"])

router = APIRouter()


@router.api_route("/search", methods=["GET"])
async def stac_search(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    page: int = 1,
    limit: int = 10,
    bbox: str = "",
    datetime: str = "",
    intersects: str = "",
    ids: str = "",
    collections: str = "",
    q: str = "",
):
    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)

    topics = collections.split()
    if any(t not in CATALOG_TOPICS for t in topics):
        raise HTTPException(
            status_code=422,
            detail=f"Collections should be one of: {', '.join(CATALOG_TOPICS)}",
        )
    if not topics:
        topics = list(CATALOG_TOPICS)

    if q:
        _gitlab_search_result: dict[str, GitlabProject] = {}
        for query in q.split(","):
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

    if ids:
        search_ids = ids.split(",")
        features = [f for f in features if f["id"] in search_ids]

    if datetime:
        search_start_dt, *_dt = datetime.split("/")
        search_start_dt = dt.fromisoformat(search_start_dt)
        search_end_dt = dt.fromisoformat(_dt[0]) if _dt else search_start_dt
        _features = []
        for f in features:
            f_start_dt = dt.fromisoformat(f["properties"]["start_datetime"])
            f_end_dt = dt.fromisoformat(f["properties"]["end_datetime"])
            if search_start_dt <= f_start_dt <= f_end_dt <= search_end_dt:
                _features.append(f)
        features = _features

    return build_stac_search_result(
        features=features,
        page=page,
        limit=limit,
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


@router.get("/{topic}/{project_id}")
async def stac_project(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    topic: TopicName,
    project_id: int,
):
    cache_key = (gitlab_config["path"], project_id)
    if (
        cache_key in PROJECT_CACHE
        and time.time() - PROJECT_CACHE[cache_key].time < PROJECT_CACHE_TIMEOUT
    ):
        return PROJECT_CACHE[cache_key].stac

    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    project = await gitlab_client.get_project(project_id)

    _topic = {"name": topic, **CATALOG_TOPICS[topic]}
    gitlab_topic = get_gitlab_topic(_topic)

    if gitlab_topic not in project["topics"]:
        raise HTTPException(
            status_code=400,
            detail=f"Project '{project_id}' do not belong to topic '{gitlab_topic}'",
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


@router.get("/{topic}/{project_path:path}")
async def stac_project_link(
    request: Request,
    gitlab_config: GitlabConfigDep,
    token: GitlabTokenDep,
    topic: TopicName,
    project_path: str,
):
    gitlab_client = GitlabClient(url=gitlab_config["url"], token=token.value)
    project = await gitlab_client.get_project(project_path)
    return RedirectResponse(
        url_for(
            request,
            "stac_project",
            path=dict(
                gitlab=gitlab_config["path"],
                topic=topic,
                project_id=project["id"],
            ),
            query={**token.query},
        )
    )
