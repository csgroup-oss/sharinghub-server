from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.utils.http import url_for

from .stac import router as stac_router

router = APIRouter(prefix="/{gitlab_base_uri}/{token}")


@router.get("/")
async def views_index(request: Request, gitlab_base_uri: str, token: str):
    return RedirectResponse(
        url_for(
            request,
            "stac_index",
            path=dict(gitlab_base_uri=gitlab_base_uri, token=token),
        )
    )


router.include_router(stac_router, prefix="/stac", tags=["stac"])
