import re

import markdown
from lxml import etree


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
