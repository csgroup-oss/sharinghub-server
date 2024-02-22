import logging
from datetime import datetime
from typing import Any

from pydantic import AnyHttpUrl, BaseModel

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
