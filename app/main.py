import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import ALLOWED_ORIGINS, API_PREFIX, DEBUG, LOGGING
from app.utils.http import AiohttpClient
from app.views import router

dictConfig(LOGGING)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    aiohttp_client = AiohttpClient()
    logger.debug("Connect http client")
    aiohttp_client.connect()
    yield
    await aiohttp_client.close()
    logger.debug("Close http client connection")


app = FastAPI(
    debug=DEBUG,
    title="STAC Dataset Proxy",
    description="STAC Dataset Proxy serves a STAC Catalog generated from Gitlab repositories.",
    version="0.1.0",
    root_path=API_PREFIX,
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
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
async def status():
    return [{"status": "ok"}]


app.include_router(router)
