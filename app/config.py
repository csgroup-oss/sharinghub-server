import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from app.utils.config import Config, cbool, clist, cpath

__all__ = [
    "DEBUG",
    "LOGGING",
    "API_PREFIX",
    "ALLOWED_ORIGINS",
    "REQUEST_TIMEOUT",
    "BROWSER_PATH",
    "ENABLE_CACHE",
    "REMOTES",
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
conf = Config.from_file(CONFIG_PATH)

########## CONFIGURATION ##########

DEBUG: bool = conf("debug", "DEBUG", default=False, cast=cbool())

DEFAULT_LOG_LEVEL: str = conf(
    "log-level", "LOG_LEVEL", default="INFO", cast=str
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

API_PREFIX: str = conf("api-prefix", "API_PREFIX", default="", cast=str)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "https://radiantearth.github.io",
]
ALLOWED_ORIGINS: list[str] = conf(
    "allowed-origins",
    "ALLOWED_ORIGINS",
    default=DEFAULT_ALLOWED_ORIGINS,
    cast=clist(sep=" "),
)
SESSION_SECRET_KEY: str = conf(
    "session.secret-key", "SESSION_SECRET_KEY", default=str(uuid.uuid4()), cast=str
)
SESSION_MAX_AGE: str = conf(
    "session.max-age", "SESSION_MAX_AGE", default=3600.0, cast=float
)

REQUEST_TIMEOUT: float = conf(
    "request-timeout", "REQUEST_TIMEOUT", default=300.0, cast=float
)

#### Browser ####

DEFAULT_BROWSER_PATH = Path(os.getcwd(), "browser", "dist")
BROWSER_PATH: Path = conf(
    "browser-path", "BROWSER_PATH", default=DEFAULT_BROWSER_PATH, cast=cpath()
)

####  STAC  ####

ENABLE_CACHE: bool = conf("cache", "ENABLE_CACHE", default=not DEBUG, cast=cbool())

# Remotes
REMOTES: dict = conf("remotes", default={}, cast=dict)

# Catalogs
CATALOG_CACHE_TIMEOUT: float = conf(
    "catalogs.cache-timeout",
    "CATALOG_CACHE_TIMEOUT",
    default=60.0 * 10,
    cast=float,
)
CATALOG_PER_PAGE: int = conf(
    "catalogs.per-page", "CATALOG_PER_PAGE", default=12, cast=int
)
CATALOG_TOPICS: dict = conf("catalogs.topics", default={}, cast=dict)

# Projects
PROJECT_CACHE_TIMEOUT: float = conf(
    "projects.cache-timeout",
    "PROJECT_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)

# Assets
DEFAULT_ASSETS_RULES = ["*.tif", "*.tiff", "*.geojson"]
ASSETS_RULES = conf(
    "assets-rules", "ASSETS_RULES", default=DEFAULT_ASSETS_RULES, cast=clist(sep=" ")
)
RELEASE_SOURCE_FORMAT: str = (
    conf("release-source-format", "RELEASE_SOURCE_FORMAT", default="zip", cast=str)
    .lower()
    .lstrip(".")
)
