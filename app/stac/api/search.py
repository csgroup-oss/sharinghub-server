import logging
import re
from datetime import datetime as dt
from functools import cached_property
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    Field,
    SerializationInfo,
    field_serializer,
    field_validator,
)
from typing_extensions import TypedDict

from app.stac.settings import STAC_SEARCH_PAGE_DEFAULT_SIZE

logger = logging.getLogger("app")


QUERY_TOPIC_PATTERN = re.compile(r"\[(?P<topic>[\w\s\-]+)\]")
QUERY_FLAG_PATTERN = re.compile(r":(?P<flag>[\w\-]+)")
QUERY_CLEAN_PATTERN = re.compile(r"(\s){2,}")

SearchMode = Literal["reference", "preview", "full"]


class STACSearchSortBy(TypedDict):
    field: str
    direction: Literal["asc", "desc"]


class STACSearchQuery(BaseModel):
    limit: Annotated[
        int,
        Field(default=STAC_SEARCH_PAGE_DEFAULT_SIZE, strict=True, gt=0),
    ]
    sortby: str | list[STACSearchSortBy] | None = Field(default=None)
    bbox: list[float] | None = Field(default_factory=list)
    datetime: str | None = Field(default=None)
    intersects: dict[str, Any] | None = Field(default=None)
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

    @cached_property
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
    matched: int | None
    returned: int
    prev: str | None
    next: str | None


def get_state_query(
    search_query: STACSearchQuery,
    exclude: list[str] | None = None,
) -> dict[str, str | int]:
    state_query = search_query.model_dump(
        mode="json",
        exclude=set(exclude) if exclude else None,
        exclude_none=True,
        exclude_defaults=True,
    )
    return {k: v for k, v in state_query.items() if v}


def parse_stac_query(query: str) -> tuple[str | None, list[str], list[str]]:
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
