import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from app.utils.config import Config, cbool, cdict, cjson, clist, cpath

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
SESSION_MAX_AGE: float = conf(
    "server.session.max-age", "SESSION_MAX_AGE", default=3600.0, cast=float
)
SESSION_AUTH_KEY = "auth"

REQUEST_TIMEOUT: float = conf(
    "server.request.timeout", "REQUEST_TIMEOUT", default=300.0, cast=float
)

#### Web UI ####

DEFAULT_WEB_UI_PATH = Path(os.getcwd(), "web-ui", "dist")
WEB_UI_PATH: Path = conf(
    "server.web-ui-path", "WEB_UI_PATH", default=DEFAULT_WEB_UI_PATH, cast=cpath()
)

####  STAC  ####

ENABLE_CACHE: bool = conf(
    "server.cache", "ENABLE_CACHE", default=not DEBUG, cast=cbool()
)

# Remotes
REMOTES: dict = conf("remotes", "REMOTES", default={}, cast=cjson())
_OAUTH_CLIENTS_IDS: dict = conf(
    env_var="OAUTH_CLIENTS_IDS", default={}, cast=cdict(sep=";")
)
_OAUTH_CLIENTS_SECRETS: dict = conf(
    env_var="OAUTH_CLIENTS_SECRETS", default={}, cast=cdict(sep=";")
)
for remote in REMOTES:
    if "oauth" not in REMOTES[remote]:
        REMOTES[remote]["oauth"] = {}
    if remote in _OAUTH_CLIENTS_IDS:
        REMOTES[remote]["oauth"]["client_id"] = _OAUTH_CLIENTS_IDS[remote]
    if remote in _OAUTH_CLIENTS_SECRETS:
        REMOTES[remote]["oauth"]["client_secret"] = _OAUTH_CLIENTS_SECRETS[remote]

# Catalogs
CATALOG_CACHE_TIMEOUT: float = conf(
    "catalogs.cache-timeout",
    "CATALOG_CACHE_TIMEOUT",
    default=60.0 * 10,
    cast=float,
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
