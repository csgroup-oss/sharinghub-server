import io
import re
from socket import AF_INET
from typing import Self
from zipfile import ZipFile

import aiohttp
import markdown
from lxml import etree


def singleton(cls):
    instances = {}

    def getinstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return getinstance


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


def parse_markdown(markdown_content: str) -> tuple[str, etree._Element, dict]:
    md = markdown.Markdown(extensions=["full_yaml_metadata"])
    md.convert(markdown_content)
    metadata = md.Meta if md.Meta else {}
    if markdown_content.startswith("---"):
        doc = markdown_content.split("---", 2)[-1].lstrip()
    else:
        doc = markdown_content
    doc_tree = etree.fromstring(f"<root>{markdown.markdown(doc)}</root>")
    return doc, doc_tree, metadata


def make_description_from_readme(markdown_content: str) -> str:
    markdown_content = re.sub(r"^#\s+(.*)\n", "", markdown_content).lstrip()
    markdown_list = markdown_content.split("\n")
    markdown_buff = []
    for line in markdown_list:
        if line.startswith("#"):
            markdown_buff.append(f"#{line}")
        else:
            markdown_buff.append(line)
    return "\n".join(markdown_buff)


class Unzippr:
    def __init__(self, response, filename, encoding="utf-8"):
        self.response = response
        self.filename = filename
        self.encoding = encoding

    async def text(self):
        with ZipFile(io.BytesIO(await self.response.read()), "r") as handle:
            # return io.TextIOWrapper(handle.open(self.filename), encoding=self.encoding)
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
