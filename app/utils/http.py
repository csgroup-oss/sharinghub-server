import re
from socket import AF_INET
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import aiohttp
from fastapi import Request

from app.config import REQUEST_TIMEOUT
from app.utils import singleton


def url_for(
    request: Request,
    name: str | None = None,
    path: dict[str, Any] = None,
    query: dict[str, Any] = None,
) -> str:
    path_params = path if path else {}
    query_params = query if query else {}

    url_ = request.url_for(name, **path_params) if name else request.url
    url_parsed = list(urlparse(str(url_)))
    url_parsed[0] = request.headers.get("X-Forwarded-Proto", request.url.scheme)

    url = urlunparse(url_parsed)
    if query_params:
        url = url_add_query_params(url, query_params)
    return url


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def is_local(uri: str) -> bool:
    return urlparse(uri).scheme in ("file", "")


def url_domain(url: str | None) -> str | None:
    if domain := urlparse(url).netloc:
        if isinstance(domain, bytes):
            domain = domain.decode()
        return domain
    return None


def urlsafe_path(path: str) -> str:
    return quote(path, safe="")


def url_add_query_params(url: str, query_params: dict) -> str:
    url_parts = list(urlparse(url))
    url_parts[4] = urlencode(dict(parse_qsl(url_parts[4])) | query_params)
    return urlunparse(url_parts)


@singleton
class AiohttpClient:
    SIZE_POOL_AIOHTTP = 100

    def __init__(self) -> None:
        self.client: aiohttp.ClientSession | None = None

    def connect(self) -> None:
        timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT if REQUEST_TIMEOUT else None
        )
        connector = aiohttp.TCPConnector(
            family=AF_INET, limit_per_host=self.SIZE_POOL_AIOHTTP
        )
        self.client = aiohttp.ClientSession(timeout=timeout, connector=connector)

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def __aenter__(self) -> aiohttp.ClientSession:
        if not self.client:
            raise RuntimeError("AiohttpClient is closed")
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False
