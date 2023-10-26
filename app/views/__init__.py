from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.dependencies import GitlabTokenDep
from app.utils.http import url_for

from .auth import router as auth_router
from .download import router as download_router
from .stac import router as stac_router

router = APIRouter(prefix="/{gitlab}")


@router.get("/")
async def views_index(
    request: Request,
    gitlab: str,
    token: GitlabTokenDep,
):
    return RedirectResponse(
        url_for(
            request,
            "stac_root",
            path=dict(gitlab=gitlab),
            query={**token.query},
        )
    )


router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(stac_router, prefix="/stac", tags=["stac"])
router.include_router(download_router, prefix="/download", tags=["download"])
