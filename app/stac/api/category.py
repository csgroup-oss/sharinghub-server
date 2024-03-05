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


def get_category_from_topics(topics: list[str]) -> Category:
    categories = get_categories()
    for category in categories:
        if category.gitlab_topic in topics:
            return category
    raise HTTPException(status_code=500, detail=f"Category not found in {topics}")


CategoryFromCollectionIdDep = Annotated[
    Category,
    Depends(get_category_from_collection_id),
]
