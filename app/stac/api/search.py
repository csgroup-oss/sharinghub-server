import logging
import re

from fastapi import HTTPException

from app.providers.client import ProviderClient
from app.providers.schemas import Project
from app.stac.api.category import Category, get_category

from .build import STACPagination, STACSearchQuery

logger = logging.getLogger("app")


QUERY_TOPIC_PATTERN = re.compile(r"\[(?P<topic>[\w\s\-]+)\]")
QUERY_FLAG_PATTERN = re.compile(r":(?P<flag>[\w\-]+)")
QUERY_CLEAN_PATTERN = re.compile(r"(\s){2,}")


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

    query, topics, flags = _parse_stac_query(" ".join(search_query.q))
    topics.append(category.gitlab_topic)

    sortby = search_query.sortby
    if sortby:
        sortby = sortby.replace("properties.", "")
        sortby = sortby.replace("sharinghub:", "")

    logger.debug(f"Query: {search_query.q}")
    logger.debug(f"Query parsed: {query=} {topics=} {flags=}")
    projects, cursor_pagination = await client.search(
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
    pagination = STACPagination(
        limit=search_query.limit,
        matched=cursor_pagination["total"],
        returned=len(projects),
        prev=cursor_pagination["start"],
        next=cursor_pagination["end"],
    )
    return projects, pagination


def _parse_stac_query(query: str) -> tuple[str | None, list[str], list[str]]:
    if query:
        topics = [
            m.groupdict()["topic"] for m in re.finditer(QUERY_TOPIC_PATTERN, query)
        ]
        flags = [m.groupdict()["flag"] for m in re.finditer(QUERY_FLAG_PATTERN, query)]
        query = re.sub(QUERY_TOPIC_PATTERN, "", query)
        query = re.sub(QUERY_FLAG_PATTERN, "", query)
        query = re.sub(QUERY_CLEAN_PATTERN, " ", query).strip()
        query = query if query else None
        return query, topics, flags
    return None, [], []
