import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from app.utils.config import Config, cbool, cjson, clist, cpath

load_dotenv()

ROOT_PATH = Path(__file__).parent

DEFAULT_CONFIG_PATH = str(ROOT_PATH / "config.yaml")
CONFIG_PATH = os.environ.get("CONFIG_PATH")
SECRET_DIR = os.environ.get("SECRET_DIR", "/var/lib/secret")
NO_DEFAULT_CONFIG = cbool()(os.environ.get("NO_DEFAULT_CONFIG", False))

_CONFIG_FILES = clist(sep=";")(CONFIG_PATH) if CONFIG_PATH else []
if not NO_DEFAULT_CONFIG:
    _CONFIG_FILES.insert(0, DEFAULT_CONFIG_PATH)
conf = Config.load(*_CONFIG_FILES, secret_dir=SECRET_DIR)

########## CONFIGURATION ##########

DEBUG: bool = conf("server.debug", "DEBUG", default=False, cast=cbool())

DEFAULT_LOG_LEVEL: str = conf(
    "server.log-level", "LOG_LEVEL", default="INFO", cast=str
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

API_PREFIX: str = conf("server.prefix", "API_PREFIX", default="", cast=str)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "https://radiantearth.github.io",
]
ALLOWED_ORIGINS: list[str] = conf(
    "server.allowed-origins",
    "ALLOWED_ORIGINS",
    default=DEFAULT_ALLOWED_ORIGINS,
    cast=clist(sep=" "),
)
SESSION_SECRET_KEY: str = conf(
    "server.session.secret-key",
    "SESSION_SECRET_KEY",
    "sessionSecretKey",
    default=str(uuid.uuid4()),
    cast=str,
)
SESSION_MAX_AGE: str = conf(
    "server.session.max-age", "SESSION_MAX_AGE", default=3600.0, cast=float
)

REQUEST_TIMEOUT: float = conf(
    "server.request.timeout", "REQUEST_TIMEOUT", default=300.0, cast=float
)

#### Browser ####

DEFAULT_BROWSER_PATH = Path(os.getcwd(), "browser", "dist")
BROWSER_PATH: Path = conf(
    "server.browser-path", "BROWSER_PATH", default=DEFAULT_BROWSER_PATH, cast=cpath()
)

####  STAC  ####

ENABLE_CACHE: bool = conf(
    "server.cache", "ENABLE_CACHE", default=not DEBUG, cast=cbool()
)

# Remotes
REMOTES: dict = conf("remotes", "REMOTES", default={}, cast=cjson())

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

# Project Assets
DEFAULT_ASSETS_RULES = ["*.tif", "*.tiff", "*.geojson"]
ASSETS_RULES = conf(
    "projects.assets.rules",
    "ASSETS_RULES",
    default=DEFAULT_ASSETS_RULES,
    cast=clist(sep=" "),
)
RELEASE_SOURCE_FORMAT: str = (
    conf(
        "projects.assets.release-source-format",
        "RELEASE_SOURCE_FORMAT",
        default="zip",
        cast=str,
    )
    .lower()
    .lstrip(".")
)
