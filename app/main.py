import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.settings import (
    ALLOWED_ORIGINS,
    API_PREFIX,
    DEBUG,
    DOCS_PATH,
    HTTP_CLIENT_TIMEOUT,
    LOGGING,
    SESSION_MAX_AGE,
    SESSION_SECRET_KEY,
    WEB_UI_PATH,
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
    title="SharingHUB API",
    description="The SharingHUB server serves STAC resources generated from Gitlab repositories.",
    version="0.1.0",
    root_path=API_PREFIX,
    docs_url="/api/docs",
    redoc_url=None,
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
    return RedirectResponse(url_for(request, "web-ui", path=dict(path="")))


@app.get("/status")
async def status():
    return [{"status": "ok"}]


app.mount(
    "/ui", StaticFiles(directory=WEB_UI_PATH, html=True, check_dir=False), name="web-ui"
)
app.mount(
    "/docs", StaticFiles(directory=DOCS_PATH, html=True, check_dir=False), name="docs"
)
app.include_router(views_router)
