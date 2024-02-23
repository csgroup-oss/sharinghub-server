from datetime import datetime
from typing import Protocol, TypedDict

from fastapi import Request
from fastapi.responses import StreamingResponse
from shapely.geometry.base import BaseGeometry

from ..schemas import Project, ProjectPreview, ProjectReference, Topic


class CursorPagination(TypedDict):
    total: int | None
    start: str | None
    end: str | None


class ProviderClient(Protocol):
    async def get_topics(self) -> list[Topic]: ...

    async def get_project(self, path: str) -> Project: ...

    async def search_references(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        limit: int,
        sort: str | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[ProjectReference], CursorPagination]: ...

    async def search_previews(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        extent: BaseGeometry | None,
        datetime_range: tuple[datetime, datetime] | None,
        limit: int,
        sort: str | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[ProjectPreview], CursorPagination]: ...

    async def search(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        extent: BaseGeometry | None,
        datetime_range: tuple[datetime, datetime] | None,
        limit: int,
        sort: str | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[Project], CursorPagination]: ...

    async def download_file(
        self,
        project_path: str,
        ref: str,
        file_path: str,
        file_cache: int,
        request: Request,
    ) -> StreamingResponse: ...

    async def download_archive(
        self, project_path: str, ref: str, format: str, request: Request
    ) -> StreamingResponse: ...
