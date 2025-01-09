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

from datetime import datetime
from typing import Protocol, TypedDict

from fastapi import Request
from fastapi.responses import StreamingResponse
from shapely.geometry.base import BaseGeometry

from app.providers.schemas import (
    Contributor,
    Project,
    ProjectPreview,
    ProjectReference,
    Topic,
    User,
)


class CursorPagination(TypedDict):
    total: int | None
    start: str | None
    end: str | None


class ProviderClient(Protocol):
    async def get_topics(self) -> list[Topic]: ...

    async def get_project(self, path: str) -> Project: ...

    async def get_contributors(
        self, project_id: int, order_by: str, request: Request | None
    ) -> list[Contributor]: ...

    async def get_users(
        self,
        order_by: str,
        request: Request | None,
    ) -> list[User]: ...

    async def get_user_avatar_url(self, request: Request) -> str | None: ...

    async def search_references(
        self,
        ids: list[str],
        query: str | None,
        topics: list[str],
        flags: list[str],
        limit: int,
        sort: tuple[str, str] | None,
        start: str | None,
        end: str | None,
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
        sort: tuple[str, str] | None,
        start: str | None,
        end: str | None,
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
        sort: tuple[str, str] | None,
        start: str | None,
        end: str | None,
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
        self,
        project_path: str,
        ref: str,
        archive_format: str,
        request: Request,
    ) -> StreamingResponse: ...
