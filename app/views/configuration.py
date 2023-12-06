from fastapi.routing import APIRouter

from app.config import STAC_CATALOGS_TOPICS, JUPYTERLAB_URL

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
                }
            }
            for topic_name, topic in STAC_CATALOGS_TOPICS.items()
        },
    }
