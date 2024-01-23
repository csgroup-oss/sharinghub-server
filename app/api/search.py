import logging
from datetime import datetime as dt

from fastapi import HTTPException

from app.api.category import get_categories, get_category
from app.api.providers import Project, ProviderClient
from app.api.stac import (
    Pagination,
    STACSearchQuery,
    get_extent,
    get_project_stac_id,
    parse_project_stac_id,
)
from app.config import STAC_CATEGORIES
from app.utils.geo import find_parent_of_hashes, hash_polygon

logger = logging.getLogger("app")


async def search_projects(
    search_query: STACSearchQuery, client: ProviderClient
) -> list[Project]:
    projects: dict[int, Project] = {}

    collections_topics: list[str] = []
    for collection_id in set(search_query.collections):
        category = get_category(collection_id)
        if category:
            collections_topics.append(category.gitlab_topic)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Collections should be one of: {', '.join(STAC_CATEGORIES)}",
            )
    collections_topics = (
        collections_topics
        if collections_topics
        else [c.gitlab_topic for c in get_categories()]
    )

    # Collections search
    for topic in collections_topics:
        projects |= {
            p.id: p for p in await client.get_projects(topic, *search_query.topics)
        }

    # Spatial extent search
    extent_search = None
    if search_query.bbox:
        bbox_geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [search_query.bbox[0], search_query.bbox[1]],
                    [search_query.bbox[2], search_query.bbox[1]],
                    [search_query.bbox[2], search_query.bbox[3]],
                    [search_query.bbox[0], search_query.bbox[3]],
                    [search_query.bbox[0], search_query.bbox[1]],
                ]
            ],
        }
        cells = hash_polygon(bbox_geojson)
        _extent_search = [" ".join(cells)]
        try:
            while True:
                cells = find_parent_of_hashes(cells)
                _extent_search.append(" ".join(cells))
        except:  # nosec B110
            pass
        for query in _extent_search:
            _search_ext = await client.search(scope="projects", query=query)
            _search_ext = [
                project
                for project in _search_ext
                if any(t in project.topics for t in collections_topics)
            ]
            extent_search = {p.id: p for p in _search_ext}

    # Free-text search
    q_search = None
    if search_query.q:
        for query in search_query.q:
            _search_q = await client.search(scope="projects", query=query)
            _search_q = [
                project
                for project in _search_q
                if any(t in project.topics for t in collections_topics)
            ]
            q_search = {p.id: p for p in _search_q}

    projects = _search_aggregate(projects, extent_search, q_search)

    # Ids search
    if search_query.ids and not projects:
        for stac_id in search_query.ids:
            stac_id_parse = parse_project_stac_id(stac_id)
            if stac_id_parse:
                category, project_id = stac_id_parse
                try:
                    project = await client.get_project(project_id)
                    if category.gitlab_topic in project.topics:
                        projects[project.id] = project
                except HTTPException as http_exc:
                    if http_exc.status_code != 404:
                        logger.exception(http_exc)
    elif search_query.ids:
        projects = {
            p.id: p
            for p in projects.values()
            if get_project_stac_id(p) in search_query.ids
        }

    # Temporal extent search
    if dt_range := search_query.datetime_range:
        search_start_dt, search_end_dt = dt_range

        def temporal_filter(project_item: tuple[int, Project]) -> bool:
            _, project = project_item
            _, temporal_extent = get_extent(project, {})
            p_start_dt = dt.fromisoformat(temporal_extent[0])
            p_end_dt = dt.fromisoformat(temporal_extent[0])
            return search_start_dt <= p_start_dt <= p_end_dt <= search_end_dt

        projects = dict(filter(temporal_filter, projects.items()))

    return list(projects.values())


def _search_aggregate(
    projects: dict[int, Project], *search_results: dict[int, Project]
) -> None:
    _projects = dict(projects)
    for search_result in search_results:
        if search_result is not None:
            if _projects:
                _projects = {
                    p_id: p for p_id, p in _projects.items() if p_id in search_result
                }
            else:
                _projects |= search_result
    return _projects


def paginate_projects(
    projects: list[Project], page: int, per_page: int
) -> tuple[list[Project], Pagination]:
    page_projects = projects[(page - 1) * per_page : page * per_page]
    pagination = Pagination(
        limit=per_page, matched=len(projects), returned=len(page_projects), page=page
    )
    return page_projects, pagination
