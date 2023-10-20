import asyncio
import enum
import logging
import time
from collections import namedtuple
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient, GitlabToken, gitlab_token
from app.api.stac import (
    build_stac_for_project,
    build_stac_root,
    build_stac_topic,
    get_gitlab_topic,
)
from app.config import (
    ASSETS_RULES,
    CATALOG_CACHE_TIMEOUT,
    CATALOG_PER_PAGE,
    CATALOG_TOPICS,
    ENABLE_CACHE,
    PROJECT_CACHE_TIMEOUT,
    RELEASE_SOURCE_FORMAT,
    REMOTES,
)
from app.utils.http import url_for

logger = logging.getLogger("app")

CATALOG_CACHE = {}
PROJECT_CACHE = {}

TopicName = enum.StrEnum("TopicName", {k: k for k in CATALOG_TOPICS})
CachedCatalog = namedtuple("CachedCatalog", ["time", "catalog"])
CachedProject = namedtuple("CachedProject", ["time", "last_activity", "stac"])

router = APIRouter()


@router.get("/")
async def stac_root(
    request: Request,
    gitlab_base_uri: str,
    token: Annotated[GitlabToken, Depends(gitlab_token)],
):
    gitlab_config = REMOTES.get(gitlab_base_uri, {})
    return build_stac_root(
        gitlab_config=gitlab_config,
        topics=CATALOG_TOPICS,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )


@router.get("/{topic_name}")
async def stac_topic(
    request: Request,
    gitlab_base_uri: str,
    token: Annotated[GitlabToken, Depends(gitlab_token)],
    topic_name: TopicName,
    page: int = 1,
):
    cache_key = (gitlab_base_uri, topic_name, token.value)
    if (
        cache_key in CATALOG_CACHE
        and time.time() - CATALOG_CACHE[cache_key].time < CATALOG_CACHE_TIMEOUT
    ):
        return CATALOG_CACHE[cache_key].catalog

    topic = {"name": topic_name, **CATALOG_TOPICS[topic_name]}

    gitlab_client = GitlabClient(base_uri=gitlab_base_uri, token=token.value)
    pagination, projects = await gitlab_client.get_projects(
        topic=get_gitlab_topic(topic), page=page, per_page=CATALOG_PER_PAGE
    )

    catalog = build_stac_topic(
        topic=topic,
        projects=projects,
        pagination=pagination,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )

    if ENABLE_CACHE:
        CATALOG_CACHE[cache_key] = CachedCatalog(time=time.time(), catalog=catalog)

    return catalog


@router.get("/{topic_name}/{project_id}")
async def stac_project(
    request: Request,
    gitlab_base_uri: str,
    token: Annotated[GitlabToken, Depends(gitlab_token)],
    topic_name: TopicName,
    project_id: int,
):
    cache_key = (gitlab_base_uri, project_id)
    if (
        cache_key in PROJECT_CACHE
        and time.time() - PROJECT_CACHE[cache_key].time < PROJECT_CACHE_TIMEOUT
    ):
        return PROJECT_CACHE[cache_key].stac

    gitlab_client = GitlabClient(base_uri=gitlab_base_uri, token=token.value)
    project = await gitlab_client.get_project(project_id)

    topic = {"name": topic_name, **CATALOG_TOPICS[topic_name]}
    gitlab_topic = get_gitlab_topic(topic)

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
            topic=topic,
            project=project,
            readme=readme,
            files=files,
            assets_rules=ASSETS_RULES,
            release=release,
            release_source_format=RELEASE_SOURCE_FORMAT,
            request=request,
            gitlab_base_uri=gitlab_base_uri,
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


@router.get("/{topic_name}/{project_path:path}")
async def stac_project_link(
    request: Request,
    gitlab_base_uri: str,
    token: Annotated[GitlabToken, Depends(gitlab_token)],
    topic_name: TopicName,
    project_path: str,
):
    gitlab_client = GitlabClient(base_uri=gitlab_base_uri, token=token.value)
    project = await gitlab_client.get_project(project_path)
    return RedirectResponse(
        url_for(
            request,
            "stac_project",
            path=dict(
                gitlab_base_uri=gitlab_base_uri,
                topic_name=topic_name,
                project_id=project["id"],
            ),
            query={**token.query},
        )
    )
