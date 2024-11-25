# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fastapi import APIRouter

from app.auth import router as auth_router
from app.configuration import router as configuration_router
from app.providers import router as providers_router
from app.stac import router as stac_router
from app.store.settings import STORE_MODE

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(configuration_router, prefix="/config", tags=["configuration"])
router.include_router(stac_router, prefix="/stac", tags=["stac"])
router.include_router(providers_router, tags=["providers"])

if STORE_MODE is not None:
    from app.store import router as store_router

    router.include_router(store_router, prefix="/store", tags=["store"])
