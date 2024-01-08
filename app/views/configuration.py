from fastapi.routing import APIRouter

from app.config import JUPYTERLAB_URL, S3_ENABLE, STAC_CATEGORIES, STAC_ROOT_CONF

router = APIRouter()


@router.get("/")
async def configuration():
    text_keys = ["title", "description"]
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
    }
