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
    "http://localhost:8080",
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

DEFAULT_WEB_UI_PATH = Path(os.getcwd(), "web-ui", "dist")
WEB_UI_PATH: Path = conf(
    "server.web-ui-path", "WEB_UI_PATH", default=DEFAULT_WEB_UI_PATH, cast=cpath()
)

DEFAULT_DOCS_PATH = Path(os.getcwd(), "docs", "build", "html")
DOCS_PATH: Path = conf(
    "server.docs-path", "DOCS_PATH", default=DEFAULT_DOCS_PATH, cast=cpath()
)

HTTP_CLIENT_TIMEOUT: float = conf(
    "server.http_client.timeout", "HTTP_CLIENT_TIMEOUT", default=300.0, cast=float
)

ENABLE_CACHE: bool = conf(
    "server.cache", "ENABLE_CACHE", default=not DEBUG, cast=cbool()
)

#### GitLab ####

GITLAB_URL: str = conf("gitlab.url", "GITLAB_URL", cast=str)
_CLIENT_ID: str | None = conf(
    "gitlab.oauth.client-id", "GITLAB_OAUTH_CLIENT_ID", cast=str
)
_CLIENT_SECRET: str | None = conf(
    "gitlab.oauth.client-secret", "GITLAB_OAUTH_CLIENT_SECRET", cast=str
)
GITLAB_OAUTH = {"client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET}
GITLAB_OAUTH = {k: v for k, v in GITLAB_OAUTH.items() if v}
GITLAB_OAUTH_DEFAULT_TOKEN: str | None = conf(
    "gitlab.oauth.default-token", "GITLAB_OAUTH_DEFAULT_TOKEN", cast=str
)

## JupyterLab ##

JUPYTERLAB_URL: str | None = conf("jupyterlab.url", "JUPYTERLAB_URL", cast=str)

####  STAC  ####

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
