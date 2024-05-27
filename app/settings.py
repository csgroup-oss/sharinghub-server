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

import os
from pathlib import Path

from dotenv import load_dotenv

from app.utils.config import Config, cbool, clist, cpath

load_dotenv(override=True)

ROOT_PATH = Path(__file__).parent

DEFAULT_CONFIG_PATH = str(ROOT_PATH / "config.yaml")
CONFIG_PATH = os.environ.get("CONFIG_PATH")
SECRET_DIR = os.environ.get("SECRET_DIR", "/var/lib/secret")
NO_DEFAULT_CONFIG = cbool()(os.environ.get("NO_DEFAULT_CONFIG", False))

_CONFIG_FILES = clist(sep=";")(CONFIG_PATH) if CONFIG_PATH else []
if not NO_DEFAULT_CONFIG:
    _CONFIG_FILES.insert(0, DEFAULT_CONFIG_PATH)
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

EXTERNAL_URLS: list = conf("external-urls", default=[], cast=clist())
ALERT_MESSAGE: dict = conf("alerts", default={}, cast=dict)

# ____ GitLab ____ #

GITLAB_URL: str = conf("gitlab.url", "GITLAB_URL", cast=str)
GITLAB_IGNORE_TOPICS: list[str] = conf(
    "gitlab.ignore.topics",
    "GITLAB_IGNORE_TOPICS",
    default=[],
    cast=clist(sep=" "),
)
TAGS_OPTIONS: dict = conf("tags", default={}, cast=dict)

# __ JupyterLab __ #

JUPYTERLAB_URL: str | None = conf("jupyterlab.url", "JUPYTERLAB_URL", cast=str)
