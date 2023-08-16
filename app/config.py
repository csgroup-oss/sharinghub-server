import os
from pathlib import Path

from dotenv import load_dotenv

from app.utils.config import cbool, clist, conf, cpath, read_config

__all__ = [
    "DEBUG",
    "LOGGING",
    "API_PREFIX",
    "ALLOWED_ORIGINS",
    "BROWSER_PATH",
    "ENABLE_CACHE",
    "REMOTES" "CATALOG_CACHE_TIMEOUT",
    "CATALOG_CACHE_TIMEOUT",
    "CATALOG_PER_PAGE",
    "CATALOG_TOPICS",
    "PROJECT_CACHE_TIMEOUT",
    "ASSETS_RULES",
    "RELEASE_SOURCE_FORMAT",
]

load_dotenv()

ROOT_PATH = Path(__file__).parent
CONFIG_PATH = os.environ.get("CONFIG_PATH", ROOT_PATH / "config.yaml")
c = read_config(CONFIG_PATH)

########## CONFIGURATION ##########

DEBUG: bool = conf(c, "debug", "DEBUG", default=False, cast=cbool())

DEFAULT_LOG_LEVEL: str = conf(
    c, "log-level", "LOG_LEVEL", default="INFO", cast=str
).upper()
LOG_LEVEL = "DEBUG" if DEBUG else DEFAULT_LOG_LEVEL
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s [%(asctime)s] %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "app": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
        }
    },
}


API_PREFIX: str = conf(c, "api-prefix", "API_PREFIX", default="", cast=str)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "https://radiantearth.github.io",
]
ALLOWED_ORIGINS: list[str] = conf(
    c,
    "allowed-origins",
    "ALLOWED_ORIGINS",
    default=DEFAULT_ALLOWED_ORIGINS,
    cast=clist(sep=" "),
)

#### Browser ####

DEFAULT_BROWSER_PATH = Path(os.getcwd(), "browser", "dist")
BROWSER_PATH: Path = conf(
    c, "browser-path", "BROWSER_PATH", default=DEFAULT_BROWSER_PATH, cast=cpath()
)

####  STAC  ####

ENABLE_CACHE: bool = conf(c, "cache", "ENABLE_CACHE", default=not DEBUG, cast=cbool())

# Remotes

REMOTES: dict = conf(c, "remotes", default={}, cast=dict)

# Catalogs
CATALOG_CACHE_TIMEOUT: float = conf(
    c,
    "catalogs.cache-timeout",
    "CATALOG_CACHE_TIMEOUT",
    default=60.0 * 10,
    cast=float,
)
CATALOG_PER_PAGE: int = conf(
    c, "catalogs.per-page", "CATALOG_PER_PAGE", default=12, cast=int
)
CATALOG_TOPICS: dict = conf(c, "catalogs.topics", default={}, cast=dict)

# Projects
PROJECT_CACHE_TIMEOUT: float = conf(
    c,
    "projects.cache-timeout",
    "PROJECT_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)

# Assets
DEFAULT_ASSETS_RULES = ["*.tif", "*.tiff", "*.geojson"]
ASSETS_RULES = conf(
    c, "assets-rules", "ASSETS_RULES", default=DEFAULT_ASSETS_RULES, cast=clist(sep=" ")
)
RELEASE_SOURCE_FORMAT: str = (
    conf(c, "release-source-format", "RELEASE_SOURCE_FORMAT", default="zip", cast=str)
    .lower()
    .lstrip(".")
)
