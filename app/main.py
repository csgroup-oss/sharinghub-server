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

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import __version__ as version
from app.settings import (
    ALLOWED_ORIGINS,
    API_PREFIX,
    DEBUG,
    HTTP_CLIENT_TIMEOUT,
    LOGGING,
    SESSION_COOKIE,
    SESSION_DOMAIN,
    SESSION_MAX_AGE,
    SESSION_SECRET_KEY,
    STATIC_FILES_PATH,
    STATIC_UI_DIRNAME,
)
from app.utils.http import AiohttpClient, url_for

from .router import router as views_router

dictConfig(LOGGING)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    aiohttp_client = AiohttpClient()
    logger.debug("Connect http client")
    aiohttp_client.connect(timeout=HTTP_CLIENT_TIMEOUT)
    yield
    await aiohttp_client.close()
    logger.debug("Close http client connection")


app = FastAPI(
    debug=DEBUG,
    title="SharingHub API",
    description="STAC resources generated from Gitlab repositories.",
    version=version,
    root_path=API_PREFIX,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie=SESSION_COOKIE,
    max_age=SESSION_MAX_AGE,
    domain=SESSION_DOMAIN,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/")
async def index(request: Request) -> RedirectResponse:
    if STATIC_FILES_PATH:
        return RedirectResponse(url_for(request, STATIC_UI_DIRNAME, path={"path": ""}))
    return RedirectResponse(url_for(request, "swagger_ui_html"))


@app.get("/status")
async def status() -> list[dict]:
    return [{"status": "ok"}]


if STATIC_FILES_PATH:
    children_dirs = [d for d in STATIC_FILES_PATH.iterdir() if d.is_dir()]
    for d in children_dirs:
        app.mount(
            f"/{d.name}",
            StaticFiles(directory=d, html=True),
            name=d.name,
        )
app.include_router(views_router, prefix="/api")
