from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import *

app = FastAPI(
    title="STAC Dataset Proxy",
    description="STAC Dataset Proxy serves a STAC Catalog generated from Gitlab repositories.",
    version="0.1.0",
    root_path=API_PREFIX,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
