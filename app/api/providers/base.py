import logging
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from fastapi.responses import StreamingResponse
from pydantic import AnyHttpUrl, BaseModel

from app.api.category import Category

logger = logging.getLogger("app")


class License(StrEnum):
    AGPL_3_0 = "AGPL-3.0"
    APACHE_2_0 = "Apache-2.0"
    BSD_2_CLAUSE = "BSD-2-Clause"
    BSD_3_CLAUSE = "BSD-3-Clause"
    BSL_1_0 = "BSL-1.0"
    CC0_1_0 = "CC0-1.0"
    EPL_2_0 = "EPL-2.0"
    GPL_2_0 = "GPL-2.0"
    GPL_3_0 = "GPL-3.0"
    LGPL_2_1 = "LGPL-2.1"
    MIT = "MIT"
    MPL_2_0 = "MPL-2.0"
    UNLICENSE = "Unlicense"


class Project(BaseModel):
    id: int
    name: str
    full_name: str
    path: str
    description: str | None
    url: AnyHttpUrl
    issues_url: AnyHttpUrl
    created_at: datetime
    last_update: datetime
    star_count: int
    topics: list[str]
    category: Category | None
    default_branch: str | None
    readme: Path | None
    license_id: License | None
    license_url: AnyHttpUrl | None


class Release(BaseModel):
    name: str
    tag: str
    description: str | None
    commit: str
    assets: list["ReleaseAsset"]


class ReleaseAsset(BaseModel):
    url: str
    format: str


class Topic(BaseModel):
    name: str
    title: str
    total_projects_count: int


class ProviderClient(Protocol):
    async def get_topics(self) -> list[Topic]:
        ...

    async def search(self, scope: str, query: Any) -> list[Project]:
        ...

    async def get_projects(self, *topics: str) -> list[Project]:
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
