import logging
import re
from datetime import datetime as dt
from typing import Annotated, TypedDict

from fastapi import HTTPException
from pydantic import (
    BaseModel,
    Field,
    Json,
    SerializationInfo,
    computed_field,
    field_serializer,
    field_validator,
)

from app.providers.client import ProviderClient
from app.providers.schemas import Project
from app.stac.api.category import Category, get_category
from app.stac.settings import STAC_SEARCH_PAGE_DEFAULT_SIZE

logger = logging.getLogger("app")


QUERY_TOPIC_PATTERN = re.compile(r"\[(?P<topic>[\w\s\-]+)\]")
QUERY_FLAG_PATTERN = re.compile(r":(?P<flag>[\w\-]+)")
QUERY_CLEAN_PATTERN = re.compile(r"(\s){2,}")


class STACSearchQuery(BaseModel):
    limit: Annotated[
        int, Field(default=STAC_SEARCH_PAGE_DEFAULT_SIZE, strict=True, gt=0)
    ]
    sortby: str | None = Field(default=None)
    bbox: list[float] | None = Field(default_factory=list)
    datetime: str | None = Field(default=None)
    intersects: Json | None = Field(default=None)
    ids: list[str] | None = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    q: list[str] | None = Field(default_factory=list)

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


class STACPagination(TypedDict):
    limit: int
    matched: int
    returned: int
    next: str | None
    prev: str | None


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


def get_state_query(
    search_query: STACSearchQuery, exclude: list[str] | None = None
) -> dict[str, str | int]:
    state_query = search_query.model_dump(
        mode="json",
        exclude=set(exclude) if exclude else None,
        exclude_none=True,
        exclude_defaults=True,
    )
    return {k: v for k, v in state_query.items() if v}


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
