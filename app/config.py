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

_GITLAB_TOPICS_FILE = Path(
    os.environ.get("GITLAB_TOPICS_FILE", Path(os.getcwd(), "resources", "topics.yaml"))
)
with open(_GITLAB_TOPICS_FILE, "r") as f:
    GITLAB_TOPICS = yaml.load(f, Loader=yaml.SafeLoader)
