import io
import re
from socket import AF_INET
from typing import Self
from urllib.parse import urlparse
from zipfile import ZipFile

import aiohttp

from app.utils import singleton


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def is_local(uri: str) -> bool:
    return urlparse(uri).scheme in ("file", "")


class Unzippr:
    def __init__(self, response, filename, encoding="utf-8"):
        self.response = response
        self.filename = filename
        self.encoding = encoding

    async def text(self):
        with ZipFile(io.BytesIO(await self.response.read()), "r") as handle:
            return handle.read(self.filename).decode(self.encoding)


@singleton
class AiohttpClient:
    SIZE_POOL_AIOHTTP = 100

    def __init__(self) -> None:
        self.client: aiohttp.ClientSession | None = None

    def connect(self) -> None:
        timeout = aiohttp.ClientTimeout(total=20)
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
        if self.client:
            self.client.headers.clear()
        return False

    def with_headers(self, headers: dict[str, str]) -> Self:
        if self.client:
            self.client.headers.extend(headers)
        return self
