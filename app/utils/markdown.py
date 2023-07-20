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


def increase_headings(markdown_content: str, incr: int = 1) -> str:
    markdown_buff = []
    for line in markdown_content.split("\n"):
        if line.startswith("#"):
            markdown_buff.append(f"{'#' * incr}{line}")
        else:
            markdown_buff.append(line)
    return "\n".join(markdown_buff)
