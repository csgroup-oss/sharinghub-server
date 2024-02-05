from datetime import datetime
from typing import Protocol, TypedDict

from fastapi.responses import StreamingResponse

from ..schemas import Project, Release, Topic


class CursorPagination(TypedDict):
    total: int | None
    start: str | None
    end: str | None


class ProviderClient(Protocol):
    async def get_topics(self) -> list[Topic]:
        ...

    async def search(
        self,
        query: str | None,
        topics: list[str],
        bbox: list[float],
        datetime_range: tuple[datetime, datetime] | None,
        stars: bool,
        limit: int,
        sort: str | None,
        prev: str | None,
        next: str | None,
    ) -> tuple[list[Project], CursorPagination]:
        ...

    async def get_project(self, path: str) -> Project:
        ...

    async def get_readme(self, project: Project) -> str:
        ...

    async def get_files(self, project: Project) -> list[str]:
        ...

    async def get_latest_release(self, project: Project) -> Release | None:
        ...

    async def download_file(
        self, project_path: str, ref: str, file_path: str
    ) -> StreamingResponse:
        ...

    async def download_archive(
        self, project_path: str, ref: str, format: str
    ) -> StreamingResponse:
        ...
