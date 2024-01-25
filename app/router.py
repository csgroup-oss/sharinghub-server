from fastapi import APIRouter

from app.auth import router as auth_router
from app.configuration import router as configuration_router
from app.providers import router as providers_router
from app.stac import router as stac_router
from app.store.settings import S3_ENABLE

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(configuration_router, prefix="/config", tags=["configuration"])
router.include_router(stac_router, prefix="/stac", tags=["stac"])
router.include_router(providers_router, tags=["providers"])

if S3_ENABLE:
    from app.store import router as store_router

    router.include_router(store_router, prefix="/store", tags=["store"])
