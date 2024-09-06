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

from typing import Any

from app.settings import conf

# Root
STAC_ROOT_CONF: dict = conf("stac.root", default={}, cast=dict)

# Categories
_STAC_CATEGORIES_LIST: list[dict[str, dict]] = conf(
    "stac.categories", default=[], cast=list
)
_STAC_CATEGORIES: dict[str, Any] = {}
for c in _STAC_CATEGORIES_LIST:
    _STAC_CATEGORIES |= c
STAC_CATEGORIES = _STAC_CATEGORIES

# Projects
STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT: str = (
    conf(
        "stac.projects.assets.release-source-format",
        "STAC_PROJECTS_ASSETS_RELEASE_SOURCE_FORMAT",
        default="zip",
        cast=str,
    )
    .lower()
    .lstrip(".")
)
STAC_PROJECTS_CACHE_TIMEOUT: float = conf(
    "stac.projects.cache-timeout",
    "STAC_PROJECTS_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)

# Search
STAC_SEARCH_PAGE_DEFAULT_SIZE: int = conf(
    "stac.search.page-size",
    "STAC_SEARCH_PAGE_DEFAULT_SIZE",
    default=12,
    cast=int,
)

# Extensions
STAC_EXTENSIONS = conf("stac.extensions", default={}, cast=dict)
