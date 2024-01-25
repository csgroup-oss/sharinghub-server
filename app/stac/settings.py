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
STAC_PROJECTS_CACHE_TIMEOUT: float = conf(
    "stac.projects.cache-timeout",
    "STAC_PROJECTS_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)
_DEFAULT_ASSETS_RULES = ["*.tif", "*.tiff", "*.geojson"]
STAC_PROJECTS_ASSETS_RULES = conf(
    "stac.projects.assets.rules",
    "STAC_PROJECTS_ASSETS_RULES",
    default=_DEFAULT_ASSETS_RULES,
    cast=clist(sep=" "),
)
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
STAC_SEARCH_CACHE_TIMEOUT: float = conf(
    "stac.search.cache-timeout",
    "STAC_SEARCH_CACHE_TIMEOUT",
    default=60.0 * 3,
    cast=float,
)
