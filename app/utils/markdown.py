# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
from functools import cache
from typing import cast

import markdown
from yaml.scanner import ScannerError

HEADING_PATTERN = re.compile(r"(#{1,6})\s+(?P<title>.*)", flags=re.MULTILINE)
IMAGE_PATTERN = re.compile(r"!\[(?P<alt>.*?)\]\((?P<src>.*?)\)")
LINK_PATTERN = re.compile(r"(?<!\!)\[(?P<text>[^\]]*)\]\((?P<href>http[s]?://[^)]+)\)")
EMPTY_LINES_PATTERN = re.compile(r"(\n){3,}")


def parse(markdown_content: str) -> tuple[str, dict]:
    try:
        md = markdown.Markdown(extensions=["full_yaml_metadata"])
        md.convert(markdown_content)
        metadata = cast(dict, md.Meta if md.Meta else {})  # type: ignore[attr-defined]
    except ScannerError:
        metadata = {}
    if markdown_content.startswith("---"):
        doc = markdown_content.split("---", 2)[-1].lstrip()
    else:
        doc = markdown_content
    return doc, metadata


@cache
def get_images(markdown_content: str) -> list[tuple[str, str]]:
    images = []
    for match_ in re.finditer(IMAGE_PATTERN, markdown_content):
        match_data = match_.groupdict()
        img_alt = match_data.get("alt", "").strip()
        img_src = match_data.get("src", "").strip()
        if all((img_alt, img_src)):
            images.append((img_alt, img_src))
    return images


@cache
def get_links(markdown_content: str) -> list[tuple[str, str]]:
    links = []
    for match_ in re.finditer(LINK_PATTERN, markdown_content):
        match_data = match_.groupdict()
        link_text = match_data.get("text", "").strip()
        link_href = match_data.get("href", "").strip()
        if all((link_text, link_href)):
            links.append((link_text, link_href))
    return links


@cache
def remove_images(markdown_content: str) -> str:
    return re.sub(IMAGE_PATTERN, "", markdown_content)


@cache
def remove_headings(markdown_content: str) -> str:
    return re.sub(HEADING_PATTERN, "", markdown_content)


@cache
def remove_links(markdown_content: str) -> str:
    return re.sub(
        LINK_PATTERN,
        lambda match: cast(str, match.groupdict().get("text")),
        markdown_content,
    )


@cache
def remove_everything_before_first_heading(markdown_content: str) -> str:
    first_heading = re.search(HEADING_PATTERN, markdown_content)
    if first_heading:
        markdown_content = markdown_content[first_heading.end() :]
    return markdown_content


@cache
def clean_new_lines(markdown_content: str) -> str:
    return re.sub(EMPTY_LINES_PATTERN, "\n\n", markdown_content).strip()
