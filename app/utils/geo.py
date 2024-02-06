import re

from shapely import geometry

BBOX_PATTERN = re.compile(
    r"bbox:\s*(?P<coordinates>(-?\d+\.\d+),\s*(-?\d+\.\d+),\s*(-?\d+\.\d+),\s*(-?\d+\.\d+))",
    flags=re.MULTILINE,
)


def bbox2polygon(bbox: list[float]) -> geometry.Polygon:
    return geometry.box(*bbox, ccw=True)


def read_bbox(text: str) -> list[float] | None:
    if bbox_match := re.search(BBOX_PATTERN, text):
        bbox_text = bbox_match.groupdict()["coordinates"]
        return [float(n) for n in bbox_text.split(",")]
    return None
