from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.api.gitlab import GitlabToken, gitlab_token
from app.utils.http import url_for

from .download import router as download_router
from .stac import router as stac_router

router = APIRouter(prefix="/{gitlab_base_uri}")


@router.get("/")
async def views_index(
    request: Request,
    gitlab_base_uri: str,
    token: Annotated[GitlabToken, Depends(gitlab_token)],
):
    return RedirectResponse(
        url_for(
            request,
            "stac_root",
            path=dict(gitlab_base_uri=gitlab_base_uri),
            query={**token.query},
        )
    )


router.include_router(stac_router, prefix="/stac", tags=["stac"])
router.include_router(download_router, prefix="/download", tags=["download"])
