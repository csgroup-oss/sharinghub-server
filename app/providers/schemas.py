# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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

import logging
from datetime import datetime
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, Field
from shapely.geometry.base import BaseGeometry

from app.stac.api.category import Category

logger = logging.getLogger("app")


class License(BaseModel):
    id: str
    url: AnyHttpUrl


class Release(BaseModel):
    name: str
    tag: str
    description: str | None
    commit: str


class ProjectReference(BaseModel):
    id: int
    name: str
    path: str
    topics: list[str]
    category: Category


class ProjectPreview(ProjectReference):
    description: str | None
    created_at: datetime
    last_update: datetime
    star_count: int
    default_branch: str | None
    readme: str
    metadata: dict[str, Any]
    extent: BaseGeometry | None

    class Config:
        arbitrary_types_allowed = True


class Project(ProjectPreview):
    full_name: str
    url: AnyHttpUrl
    bug_tracker: AnyHttpUrl
    license: License | None
    last_commit: str | None
    files: list[str] | None
    latest_release: Release | None
    # 0 for no access
    # 1 for read-only (visitor)
    # 2 for modification allowed (contributor)
    # 3 for management permissions (administrator)
    access_level: int = Field(ge=0, le=3)


class Topic(BaseModel):
    name: str
    title: str
    total_projects_count: int
