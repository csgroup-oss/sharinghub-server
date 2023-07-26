import asyncio
import enum
import time
from collections import namedtuple

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabClient
from app.api.stac import build_collection, build_root_catalog, build_topic_catalog
from app.config import (
    CATALOG_CACHE_TIMEOUT,
    CATALOG_TOPICS,
    COLLECTION_CACHE_TIMEOUT,
    DEBUG,
)

router = APIRouter(prefix="/{gitlab_base_uri}/{token}", tags=["stac"])

TopicName = enum.StrEnum("TopicName", {k: k for k in CATALOG_TOPICS})

CATALOG_CACHE = {}
COLLECTION_CACHE = {}

CachedCatalog = namedtuple("CachedCatalog", ["time", "catalog"])
CachedCollection = namedtuple(
    "CachedCollection", ["time", "last_activity", "collection"]
)


@router.get("/")
async def index(request: Request, gitlab_base_uri: str, token: str):
    return RedirectResponse(
        request.url_for("root_catalog", gitlab_base_uri=gitlab_base_uri, token=token)
    )


@router.get("/catalog.json")
async def root_catalog(request: Request, gitlab_base_uri: str, token: str):
    return build_root_catalog(
        topics=CATALOG_TOPICS,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )


@router.get("/{topic_name}/catalog.json")
async def topic_catalog(
    request: Request,
    gitlab_base_uri: str,
    token: str,
    topic_name: TopicName,
):
    cache_key = (gitlab_base_uri, topic_name, token)
    if (
        not DEBUG
        and cache_key in CATALOG_CACHE
        and time.time() - CATALOG_CACHE[cache_key].time < CATALOG_CACHE_TIMEOUT
    ):
        return CATALOG_CACHE[cache_key].catalog

    gitlab_client = GitlabClient(base_uri=gitlab_base_uri, token=token)
    projects = await gitlab_client.get_projects(topic_name)

    catalog = build_topic_catalog(
        name=topic_name,
        fields=CATALOG_TOPICS.get(topic_name),
        projects=projects,
        request=request,
        gitlab_base_uri=gitlab_base_uri,
        token=token,
    )
    CATALOG_CACHE[cache_key] = CachedCatalog(time=time.time(), catalog=catalog)
    return catalog


@router.get("/{topic_name}/{project_path:path}/collection.json")
async def project_collection(
    request: Request,
    gitlab_base_uri: str,
    token: str,
    topic_name: TopicName,
    project_path: str,
):
    cache_key = (gitlab_base_uri, project_path)
    if (
        not DEBUG
        and cache_key in COLLECTION_CACHE
        and time.time() - COLLECTION_CACHE[cache_key].time < COLLECTION_CACHE_TIMEOUT
    ):
        return COLLECTION_CACHE[cache_key].collection

    gitlab_client = GitlabClient(base_uri=gitlab_base_uri, token=token)
    project = await gitlab_client.get_project(project_path)

    if topic_name not in project["topics"]:
        raise HTTPException(
            status_code=400,
            detail=f"Project '{project_path}' do not belong to topic '{topic_name}'",
        )

    if (
        not DEBUG
        and cache_key in COLLECTION_CACHE
        and COLLECTION_CACHE[cache_key].last_activity == project["last_activity_at"]
    ):
        collection = COLLECTION_CACHE[cache_key].collection
        COLLECTION_CACHE[cache_key] = CachedCollection(
            time=time.time(),
            last_activity=project["last_activity_at"],
            collection=collection,
        )
        return collection

    readme, members, files, release = await asyncio.gather(
        gitlab_client.get_readme(project),
        gitlab_client.get_members(project),
        gitlab_client.get_files(project),
        gitlab_client.get_latest_release(project),
    )

    try:
        collection = build_collection(
            topic_name=topic_name,
            project=project,
            readme=readme,
            members=members,
            files=files,
            release=release,
            request=request,
            gitlab_base_uri=gitlab_base_uri,
            token=token,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    COLLECTION_CACHE[cache_key] = CachedCollection(
        time=time.time(),
        last_activity=project["last_activity_at"],
        collection=collection,
    )
    return collection
