import logging
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
    SESSION_MAX_AGE,
    SESSION_SECRET_KEY,
    STATIC_FILES_PATH,
)
from app.utils.http import AiohttpClient, url_for

from .router import router as views_router

dictConfig(LOGGING)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    aiohttp_client = AiohttpClient()
    logger.debug("Connect http client")
    aiohttp_client.connect(timeout=HTTP_CLIENT_TIMEOUT)
    yield
    await aiohttp_client.close()
    logger.debug("Close http client connection")


app = FastAPI(
    debug=DEBUG,
    title="SharingHub API",
    description="The SharingHub server serves STAC resources generated from Gitlab repositories.",
    version=version,
    root_path=API_PREFIX,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=SESSION_MAX_AGE,
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
async def index(request: Request):
    if STATIC_FILES_PATH:
        return RedirectResponse(url_for(request, "statics", path=dict(path="")))
    return RedirectResponse(url_for(request, "swagger_ui_html"))


@app.get("/status")
async def status():
    return [{"status": "ok"}]


if STATIC_FILES_PATH:
    app.mount(
        "/ui",
        StaticFiles(directory=STATIC_FILES_PATH, html=True),
        name="statics",
    )
app.include_router(views_router, prefix="/api")
