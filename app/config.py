import os
from pathlib import Path

import yaml

DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1"]

LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
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

API_PREFIX = os.environ.get("API_PREFIX", "")
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    " ".join(f"http://localhost:{p}" for p in [3000, 5000, 8000, 9000]),
).split() + [
    "https://radiantearth.github.io",  # STAC Browser
]

#### STAC ####

STAC_CONFIG_PATH = os.environ.get(
    "STAC_CONFIG_PATH", Path(os.getcwd(), "resources", "stac_config.yaml")
)
with open(STAC_CONFIG_PATH, "r") as f:
    STAC_CONFIG = yaml.load(f, Loader=yaml.SafeLoader)

# Catalogs
CATALOG_CACHE_TIMEOUT = float(os.environ.get("CATALOG_CACHE_TIMEOUT", 60.0 * 5))
CATALOG_TOPICS = STAC_CONFIG.get("topics", {})

# Collections

COLLECTION_CACHE_TIMEOUT = float(os.environ.get("COLLECTION_CACHE_TIMEOUT", 60.0 * 5))

# Assets
ASSETS_PATTERNS = os.environ.get(
    "ASSETS_PATTERNS",
    "*.tif *.tiff *.geojson",
).split()
RELEASE_SOURCE_FORMAT = (
    os.environ.get("RELEASE_SOURCE_FORMAT", "zip").lower().lstrip(".")
)
