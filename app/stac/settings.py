from app.settings import conf
from app.utils.config import clist

# Root
STAC_ROOT_CONF: dict = conf("stac.root", default={}, cast=dict)

# Categories
STAC_CATEGORIES_PAGE_DEFAULT_SIZE: int = conf(
    "stac.categories.page-size",
    "STAC_CATEGORIES_PAGE_DEFAULT_SIZE",
    default=12,
    cast=int,
)
STAC_CATEGORIES: dict = conf("stac.categories.definitions", default={}, cast=dict)

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
STAC_SEARCH_CACHE_TIMEOUT: float = conf(
    "stac.search.cache-timeout",
    "STAC_SEARCH_CACHE_TIMEOUT",
    default=60.0 * 3,
    cast=float,
)

# Extensions
STAC_EXTENSIONS = conf("stac.extensions", default={}, cast=dict)
