# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
from typing import Literal

import aiohttp
import yaml
from fastapi import HTTPException, Request
from fastapi.routing import APIRouter

from app.auth import GitlabTokenDep
from app.providers.client import CursorPagination, GitlabClient
from app.providers.schemas import Project, RegisteredModel
from app.settings import ENABLE_CACHE, GITLAB_URL, MLFLOW_TYPE
from app.stac.api.category import (
    Category,
    CategoryFromCollectionIdDep,
    get_categories,
    get_category,
)
from app.utils import geo
from app.utils.cache import cache
from app.utils.http import AiohttpClient, url_add_query_params, urlsafe_path

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
    user: str | None = await cache.get(token.value, namespace="user")
    if not user:
        user = await gitlab_client.get_user()
        await cache.set(token.value, user, namespace="user")

    if category not in project.categories:
        raise HTTPException(
            status_code=400,
            detail=f"Category mismatch for project '{project.path}', "
            f"asked '{category.id}' but got "
            f"{', '.join(c.id for c in project.categories)} instead",
        )

    cache_key = ("stac", user, project.path)
    cached_stac = await cache.get(cache_key, namespace="project")
    if cached_stac and cached_stac["checksum"] == _get_project_checksum(project):
        logger.debug(
            f"Read project stac from cache '{project.path}' (no changes detected)",
        )
        await cache.set(
            cache_key,
            cached_stac,
            ttl=int(STAC_PROJECTS_CACHE_TIMEOUT),
            namespace="project",
        )
        return cached_stac["stac"]

    await _resolve_license(project, gitlab_client)
    await _collect_containers_tags(project, gitlab_client)
    await _collect_registered_models(
        project,
        mlflow_type=MLFLOW_TYPE,
        auth_token=token.value,
    )

    project_stac = build_stac_item(
        project=project,
        category=category,
        request=request,
        token=token,
    )
    if ENABLE_CACHE:
        logger.debug(f"Write stac '{feature_id}' in cache")
        cached_stac = {
            "checksum": _get_project_checksum(project),
            "stac": project_stac,
        }
        await cache.set(
            cache_key,
            cached_stac,
            ttl=int(STAC_PROJECTS_CACHE_TIMEOUT),
            namespace="project",
        )

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
                build_stac_item_reference(p, category, request=request, token=token)
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
                build_stac_item_preview(p, category, request=request, token=token)
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
                *(_collect_containers_tags(p, gitlab_client) for p in projects),
                *(
                    _collect_registered_models(
                        p,
                        mlflow_type=MLFLOW_TYPE,
                        auth_token=token.value,
                    )
                    for p in projects
                ),
            )
            features = [
                build_stac_item(p, category, request=request, token=token)
                for p in projects
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


async def _collect_containers_tags(project: Project, client: GitlabClient) -> None:
    for container in project.containers:
        container.tags = await client.get_container_tags(container)


async def _collect_registered_models(
    project: Project,
    mlflow_type: Literal["mlflow", "mlflow-sharinghub", "gitlab"],
    auth_token: str,
) -> None:
    if project.mlflow:
        registered_models = []
        match mlflow_type:
            case "mlflow-sharinghub":
                registered_models.extend(
                    await _get_registered_models(
                        project.mlflow.tracking_uri, auth_token=auth_token
                    )
                )
        project.mlflow.registered_models = registered_models


async def _get_registered_models(
    mlflow_url: str, auth_token: str
) -> list[RegisteredModel]:
    mlflow_api_url = mlflow_url + "api/2.0/mlflow"
    headers = {"Authorization": f"Bearer {auth_token}"}

    registered_models: list[RegisteredModel] = []
    async with AiohttpClient() as client:
        search_req = await client.get(
            url=mlflow_api_url + "/registered-models/search", headers=headers
        )
        if not search_req.ok:
            return registered_models

        search_data = await search_req.json()
        all_registered_models = search_data.get("registered_models", [])
        for rm_data in all_registered_models:
            # Read latest version metadata
            latest_versions = rm_data.get("latest_versions", [])
            if not latest_versions:
                continue
            latest_version = latest_versions[0]

            # Determine model informations
            model_name = latest_version["name"]
            model_version = latest_version["version"]
            mlflow_uri = f"models:/{model_name}/{model_version}"
            mlflow_run = latest_version["run_id"]
            model_url = (
                f"{mlflow_url}#/models/"
                f"{urlsafe_path(model_name)}/versions/{model_version}"
            )

            model_artifact_path = await _get_model_artifact_path(
                mlflow_url=mlflow_url,
                mlflow_run=mlflow_run,
                mlflow_source=latest_version["source"],
                client=client,
                headers=headers,
            )
            if not model_artifact_path:
                continue

            registered_models.append(
                RegisteredModel(
                    name=model_name,
                    version=model_version,
                    web_url=model_url,
                    mlflow_uri=mlflow_uri,
                    artifact_path=model_artifact_path,
                    download_url=url_add_query_params(
                        mlflow_url + "get-artifact",
                        {"path": model_artifact_path, "run_uuid": mlflow_run},
                    ),
                )
            )
    return registered_models


async def _get_model_artifact_path(
    mlflow_url: str,
    mlflow_run: str,
    mlflow_source: str,
    client: aiohttp.ClientSession,
    headers: dict[str, str],
) -> str | None:
    # Resolve model artifacts dir path
    source_artifacts_split = mlflow_source.split("/artifacts/", 1)
    if len(source_artifacts_split) != 2:  # noqa: PLR2004
        return None
    artifact_path = source_artifacts_split[1]

    # Retrieve model mlflow metadata
    model_metadata_req = await client.get(
        url=url_add_query_params(
            mlflow_url + "get-artifact",
            {"path": artifact_path + "/MLmodel", "run_uuid": mlflow_run},
        ),
        headers=headers,
    )
    if not model_metadata_req.ok:
        return None
    model_metadata_content = await model_metadata_req.text()
    model_metadata = yaml.load(model_metadata_content, Loader=yaml.SafeLoader)

    python_flavor = model_metadata.get("flavors", {}).get("python_function", {})
    if not python_flavor:
        return None

    _model_path = python_flavor.get("model_path")
    _data = python_flavor.get("data")

    model_path: str | None = _model_path or _data
    if not model_path:
        return None

    return artifact_path + "/" + model_path
