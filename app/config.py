import os
from pathlib import Path

import yaml

DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1"]

API_PREFIX = os.environ.get("API_PREFIX", "")
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    " ".join(f"http://localhost:{p}" for p in [3000, 5000, 8000, 9000]),
).split() + [
    "https://radiantearth.github.io",  # STAC Browser
]

# Catalogs
CATALOG_CACHE_TIMEOUT = float(os.environ.get("CATALOG_CACHE_TIMEOUT", 60.0 * 5))
_CATALOG_TOPICS_FILE = Path(
    os.environ.get("CATALOG_TOPICS_FILE", Path(os.getcwd(), "resources", "topics.yaml"))
)
with open(_CATALOG_TOPICS_FILE, "r") as f:
    CATALOG_TOPICS = yaml.load(f, Loader=yaml.SafeLoader)

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
