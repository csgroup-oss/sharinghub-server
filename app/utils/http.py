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

import re
from enum import StrEnum, auto
from socket import AF_INET
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import aiohttp
from fastapi import Request

from app.utils import singleton


class HttpMethod(StrEnum):
    GET = auto()
    POST = auto()
    PUT = auto()
    DELETE = auto()
    PATCH = auto()
    HEAD = auto()
    OPTIONS = auto()


def url_for(
    request: Request,
    name: str | None = None,
    path: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
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


def clean_url(url: str, trailing_slash: bool = True) -> str:
    u = urlparse(url)
    if u.scheme in ["http", "https"] and u.netloc:
        return url.removesuffix("/") + ("/" if trailing_slash else "")
    msg = f"Not a valid URL: '{url}'"
    raise ValueError(msg)


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

    def connect(self, timeout: float) -> None:
        client_timeout = aiohttp.ClientTimeout(total=timeout if timeout else None)
        connector = aiohttp.TCPConnector(
            family=AF_INET,
            limit_per_host=self.SIZE_POOL_AIOHTTP,
        )
        self.client = aiohttp.ClientSession(timeout=client_timeout, connector=connector)

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None

    async def __aenter__(self) -> aiohttp.ClientSession:
        if not self.client:
            msg = "AiohttpClient is closed"
            raise RuntimeError(msg)
        return self.client

    async def __aexit__(self, *exc: object) -> bool:
        return False
