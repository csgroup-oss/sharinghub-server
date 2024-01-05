from fastapi.routing import APIRouter

from app.config import JUPYTERLAB_URL, STAC_CATALOGS_TOPICS, STAC_ROOT_CONF

router = APIRouter()


@router.get("/")
async def configuration():
    text_keys = ["title", "description"]
    exclude_keys = ["locales"]
    return {
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
        "topics": {
            topic_name: {
                **{
                    k: v
                    for k, v in topic.items()
                    if k not in ["features", *text_keys, *exclude_keys]
                },
                "locales": {
                    "en": {k: v for k, v in topic.items() if k in text_keys},
                    **{
                        locale: {k: v for k, v in translation.items()}
                        for locale, translation in topic.get("locales", {}).items()
                    },
                },
            }
            for topic_name, topic in STAC_CATALOGS_TOPICS.items()
        },
    }
