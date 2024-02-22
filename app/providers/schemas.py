import logging
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AnyHttpUrl, BaseModel

from app.stac.api.category import Category

logger = logging.getLogger("app")


class LicenseIdentifier(StrEnum):
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


class License(BaseModel):
    id: LicenseIdentifier
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


class Project(ProjectPreview):
    full_name: str
    url: AnyHttpUrl
    bug_tracker: AnyHttpUrl
    license: License | None
    last_commit: str | None
    files: list[str] | None
    latest_release: Release | None


class Topic(BaseModel):
    name: str
    title: str
    total_projects_count: int
