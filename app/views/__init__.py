from fastapi.routing import APIRouter

from .auth import router as auth_router
from .configuration import router as configuration_router
from .download import router as download_router
from .proxy import router as proxy_router
from .stac import router as stac_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(configuration_router, prefix="/config", tags=["configuration"])
router.include_router(stac_router, prefix="/stac", tags=["stac"])
router.include_router(download_router, prefix="/download", tags=["download"])
router.include_router(proxy_router, prefix="/api", tags=["proxy"])
