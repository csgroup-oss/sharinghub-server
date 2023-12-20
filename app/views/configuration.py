from fastapi.routing import APIRouter

from app.config import JUPYTERLAB_URL, STAC_CATALOGS_TOPICS, STAC_ROOT_CONF

router = APIRouter()


@router.get("/")
async def configuration():
    text_keys = ["title", "description"]
    return {
        "jupyterlab": {
            "url": JUPYTERLAB_URL,
        },
        "topics": {
            topic_name: {
                "locales": {
                    "en": {k: v for k, v in topic.items() if k in text_keys},
                    **{
                        locale: {k: v for k, v in translation.items() if k in text_keys}
                        for locale, translation in topic.get("locales", {}).items()
                    },
                },
                "logo": topic.get("logo", {}),
            }
            for topic_name, topic in STAC_CATALOGS_TOPICS.items()
        },
        "root": {
            **{
                k: v
                for k, v in STAC_ROOT_CONF.items()
                if k not in ["locales", "description"]
            },
            "locales": {
                "en": {
                    k: v
                    for k, v in STAC_ROOT_CONF.items()
                    if k not in ["locales", "title", "id"]
                },
                **{
                    locale: {k: v for k, v in translation.items()}
                    for locale, translation in STAC_ROOT_CONF.get("locales", {}).items()
                },
            },
        },
    }
