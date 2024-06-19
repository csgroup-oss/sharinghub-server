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

from fastapi.routing import APIRouter

from app.settings import (
    ALERT_MESSAGE,
    DOCS_URL,
    EXTERNAL_URLS,
    GITLAB_URL,
    JUPYTERLAB_URL,
    MLFLOW_URL,
    SPACES,
)
from app.stac.settings import STAC_CATEGORIES, STAC_ROOT_CONF
from app.store.settings import S3_ENABLE

router = APIRouter()


@router.get("/")
async def configuration() -> dict:
    text_keys = ["title", "description", "name"]
    exclude_keys = ["locales"]
    return {
        "store": S3_ENABLE,
        "gitlab": {"url": GITLAB_URL},
        "jupyterlab": {"url": JUPYTERLAB_URL},
        "mlflow": {"url": MLFLOW_URL},
        "docs": {"url": DOCS_URL},
        "spaces": {**SPACES},
        "root": {
            **{
                k: v
                for k, v in STAC_ROOT_CONF.items()
                if k not in ["id", *text_keys, *exclude_keys]
            },
            "locales": {
                "en": {k: v for k, v in STAC_ROOT_CONF.items() if k in text_keys},
                **{
                    locale: dict(translation)
                    for locale, translation in STAC_ROOT_CONF.get("locales", {}).items()
                },
            },
        },
        "categories": {
            category_name: {
                **{
                    k: v
                    for k, v in category.items()
                    if k not in ["features", *text_keys, *exclude_keys]
                },
                "locales": {
                    "en": {k: v for k, v in category.items() if k in text_keys},
                    **{
                        locale: dict(translation)
                        for locale, translation in category.get("locales", {}).items()
                    },
                },
            }
            for category_name, category in STAC_CATEGORIES.items()
        },
        "external_urls": normalize_external_urls(EXTERNAL_URLS, text_keys),
        "alert_info": {
            **{k: v for k, v in ALERT_MESSAGE.items() if k not in ["message", "title"]},
            "locales": {
                "en": {
                    k: v for k, v in ALERT_MESSAGE.items() if k in ["message", "title"]
                },
                **{
                    locale: dict(translation)
                    for locale, translation in ALERT_MESSAGE.get("locales", {}).items()
                },
            },
        },
    }


def normalize_external_urls(array: list[dict], text_keys: list[str]) -> list[dict]:
    def mapping(link: dict) -> dict:
        dropdown = link.get("dropdown", [])
        if not dropdown:
            return {
                **{k: v for k, v in link.items() if k not in text_keys},
                "locales": {
                    "en": {k: v for k, v in link.items() if k in text_keys},
                    **dict(link.get("locales", {})),
                },
            }
        return {
            **{k: v for k, v in link.items() if k not in text_keys},
            "locales": {
                "en": {k: v for k, v in link.items() if k in text_keys},
                **dict(link.get("locales", {})),
            },
            "dropdown": normalize_external_urls(dropdown, text_keys),
        }

    return list(map(mapping, array))
