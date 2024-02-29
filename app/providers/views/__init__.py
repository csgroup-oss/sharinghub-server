from fastapi import APIRouter

from .download import router as download_router
from .proxy import router as proxy_router

router = APIRouter()
router.include_router(download_router, prefix="/download", tags=["download"])
router.include_router(proxy_router, prefix="/proxy", tags=["proxy"])
