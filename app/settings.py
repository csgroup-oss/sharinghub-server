# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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

import os
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

from app.utils.config import Config, cbool, clist, cpath

load_dotenv(override=True)

ROOT_PATH = Path(__file__).parent
DEFAULT_CONFIG_PATH = str(ROOT_PATH / "config.yaml")

CONFIG_PATH = os.environ.get("CONFIG_PATH")
SECRET_DIR = os.environ.get("SECRET_DIR", "/var/lib/secret")

_CONFIG_FILES = clist(sep=";")(CONFIG_PATH) if CONFIG_PATH else []
if not _CONFIG_FILES:
    _CONFIG_FILES.append(DEFAULT_CONFIG_PATH)
conf = Config.load(*_CONFIG_FILES, secret_dir=SECRET_DIR)

# ____________ SETTINGS ____________ #

DEBUG: bool = conf("server.debug", "DEBUG", default=False, cast=cbool())

DEFAULT_LOG_LEVEL: str = conf(
    "server.log-level",
    "LOG_LEVEL",
    default="INFO",
    cast=str,
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
        },
    },
}

API_PREFIX: str = conf("server.prefix", "API_PREFIX", default="", cast=str)
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://localhost:8081",
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
    default="",
    cast=str,
)
SESSION_COOKIE: str = conf(
    "server.session.cookie",
    "SESSION_COOKIE",
    default="sharinghub-session",
    cast=str,
)
SESSION_DOMAIN: str | None = conf(
    "server.session.domain",
    "SESSION_DOMAIN",
    default=None,
    cast=str,
)
SESSION_MAX_AGE: float = conf(
    "server.session.max-age",
    "SESSION_MAX_AGE",
    default=3600.0,
    cast=float,
)

STATIC_FILES_PATH: Path | None = conf(
    "server.statics",
    "STATIC_FILES_PATH",
    default=None,
    cast=cpath(),
)
STATIC_UI_DIRNAME: str = conf(
    "server.statics-ui", "STATIC_UI_DIRNAME", default="ui", cast=str
)

HTTP_CLIENT_TIMEOUT: float = conf(
    "server.http_client.timeout",
    "HTTP_CLIENT_TIMEOUT",
    default=300.0,
    cast=float,
)

ENABLE_CACHE: bool = conf(
    "server.cache",
    "ENABLE_CACHE",
    default=not DEBUG,
    cast=cbool(),
)

CHECKER_CACHE_TIMEOUT: float = conf(
    "checker.cache-timeout",
    "CHECKER_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)

EXTERNAL_URLS: list = conf("external-urls", default=[], cast=clist())
ALERT_MESSAGE: dict = conf("alerts", default={}, cast=dict)

_services: dict[str, dict[str, Any]] = conf("services", default={}, cast=dict)
for _service in _services.values():
    _url = urlparse(_service["url"])
    _service["path"] = _service.get("path", _url.path)
    _service["status-path"] = _service["path"].removesuffix("/") + _service.get(
        "status", "/status"
    )

    _parsed_status_url = list(_url)
    _parsed_status_url[2] = _service["status-path"]
    _service["status"] = urlunparse(_parsed_status_url)

    _parsed_openapi_url = list(_url)
    _parsed_openapi_url[2] = _parsed_openapi_url[2].removesuffix("/") + _service.get(
        "openapi", "/openapi.json"
    )
    _service["openapi"] = urlunparse(_parsed_openapi_url)

SERVICES = _services

# ____ GitLab ____ #

GITLAB_URL: str = conf("gitlab.url", "GITLAB_URL", cast=str)
GITLAB_IGNORE_TOPICS: list[str] = conf(
    "gitlab.ignore.topics",
    "GITLAB_IGNORE_TOPICS",
    default=[],
    cast=clist(sep=" "),
)
TAGS_OPTIONS: dict = conf("tags", default={}, cast=dict)

# ____ MLflow ____ #

MLFLOW_TYPE: Literal["mlflow", "mlflow-sharinghub", "gitlab"] = conf(
    "mlflow.type", "MLFLOW_TYPE", default="mlflow-sharinghub", cast=str
)
MLFLOW_URL: str | None = conf("mlflow.url", "MLFLOW_URL", cast=str)

# __ URLS __ #

JUPYTERLAB_URL: str | None = conf("jupyterlab.url", "JUPYTERLAB_URL", cast=str)
DOCS_URL: str | None = conf("docs.url", "DOCS_URL", cast=str)

# __ DEPLOYMENT SPACES ___ #

SPACES: dict = conf("spaces", "SPACES", default={}, cast=dict)

# __ WIZARD ___

WIZARD_URL: str | None = conf("services.wizard.url", "WIZARD_URL", cast=str)
