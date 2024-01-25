from fastapi.routing import APIRouter

from app.settings import ALERT_MESSAGE, EXTERNAL_URLS, JUPYTERLAB_URL
from app.stac.settings import STAC_CATEGORIES, STAC_ROOT_CONF
from app.store.settings import S3_ENABLE

router = APIRouter()


@router.get("/")
async def configuration():
    text_keys = ["title", "description", "name"]
    exclude_keys = ["locales"]
    return {
        "store": S3_ENABLE,
        "jupyterlab": {
            "url": JUPYTERLAB_URL,
        },
        "root": {
            **{
                k: v
                for k, v in STAC_ROOT_CONF.items()
                if k not in ["id", *text_keys, *exclude_keys]
            },
            "locales": {
                "en": {k: v for k, v in STAC_ROOT_CONF.items() if k in text_keys},
                **{
                    locale: {k: v for k, v in translation.items()}
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
                        locale: {k: v for k, v in translation.items()}
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
                    locale: {k: v for k, v in translation.items()}
                    for locale, translation in ALERT_MESSAGE.get("locales", {}).items()
                },
            },
        },
    }


def normalize_external_urls(array: list[dict], text_keys: list[str]) -> list[dict]:
    def mapping(link: dict):
        if not link.get("dropdown"):
            return {
                **{k: v for k, v in link.items() if k not in text_keys},
                "locales": {
                    "en": {k: v for k, v in link.items() if k in text_keys},
                    **{k: v for k, v in link.get("locales", {}).items()},
                },
            }
        else:
            return {
                **{k: v for k, v in link.items() if k not in text_keys},
                "locales": {
                    "en": {k: v for k, v in link.items() if k in text_keys},
                    **{k: v for k, v in link.get("locales", {}).items()},
                },
                "dropdown": normalize_external_urls(link.get("dropdown"), text_keys),
            }

    return list(map(mapping, array))
