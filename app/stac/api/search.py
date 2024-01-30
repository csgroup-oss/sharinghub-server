import logging

from fastapi import HTTPException

from app.providers.client import ProviderClient
from app.providers.schemas import Project
from app.stac.api.category import Category, get_category

from .build import STACPagination, STACSearchQuery

logger = logging.getLogger("app")


async def search_projects(
    client: ProviderClient,
    search_query: STACSearchQuery,
    category: Category | None,
    prev: str | None,
    next: str | None,
) -> tuple[list[Project], STACPagination]:
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

    topics = [category.gitlab_topic, *search_query.topics]

    sortby = search_query.sortby
    if sortby:
        sortby = sortby.replace("properties.", "")
        sortby = sortby.replace("sharinghub:", "")

    projects, cursor_pagination = await client.search(
        query=" ".join(search_query.q),
        topics=topics,
        bbox=search_query.bbox,
        datetime_range=search_query.datetime_range,
        limit=search_query.limit,
        sort=sortby,
        prev=prev,
        next=next,
    )
    pagination = STACPagination(
        limit=search_query.limit,
        matched=cursor_pagination["total"],
        returned=len(projects),
        prev=cursor_pagination["start"],
        next=cursor_pagination["end"],
    )
    return projects, pagination
