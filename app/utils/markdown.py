import re
from functools import cache

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
        metadata = md.Meta if md.Meta else {}
    except ScannerError:
        metadata = {}
    if markdown_content.startswith("---"):
        doc = markdown_content.split("---", 2)[-1].lstrip()
    else:
        doc = markdown_content
    return doc, metadata


@cache
def increase_headings(markdown_content: str, incr: int = 1) -> str:
    markdown_buff = []
    for line in markdown_content.split("\n"):
        if line.startswith("#"):
            markdown_buff.append(f"{'#' * incr}{line}")
        else:
            markdown_buff.append(line)
    return "\n".join(markdown_buff)


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
        lambda match: match.groupdict().get("text"),
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
