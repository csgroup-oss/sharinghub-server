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
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field

from app.stac.settings import STAC_CATEGORIES

logger = logging.getLogger("app")


class FeatureVal(StrEnum):
    ENABLE = "enable"
    DISABLE = "disable"


class Category(BaseModel):
    id: str
    title: str
    description: str | None = Field(default=None)
    gitlab_topic: str
    features: dict[str, FeatureVal] = Field(default_factory=dict)
    icon: AnyHttpUrl | None = Field(default=None)
    logo: AnyHttpUrl | None = Field(default=None)
    assets: list[str | dict[str, Any]] = Field(default_factory=list)


def get_category(category_id: str) -> Category | None:
    if category_id in STAC_CATEGORIES:
        return Category(id=category_id, **STAC_CATEGORIES[category_id])
    return None


def get_categories() -> list[Category]:
    return [
        get_category_from_collection_id(collection_id)
        for collection_id in STAC_CATEGORIES
    ]


def get_category_from_collection_id(collection_id: str) -> Category:
    category = get_category(category_id=collection_id)
    if not category:
        logger.error(
            f"Collection '{collection_id}' requested but its configuration is missing.",
        )
        raise HTTPException(status_code=404, detail="Collection not found")

    return category


def get_categories_from_topics(topics: list[str]) -> list[Category]:
    categories = [c for c in get_categories() if c.gitlab_topic in topics]
    if not categories:
        raise HTTPException(status_code=500, detail=f"Category not found in {topics}")
    return categories


CategoryFromCollectionIdDep = Annotated[
    Category,
    Depends(get_category_from_collection_id),
]
