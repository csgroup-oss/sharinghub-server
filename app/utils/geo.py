import re

from shapely import geometry

BBOX_PATTERN = re.compile(
    r"bbox:\s*(?P<coordinates>(-?\d+\.\d+),\s*(-?\d+\.\d+),\s*(-?\d+\.\d+),\s*(-?\d+\.\d+))",
    flags=re.MULTILINE,
)


def read_bbox(text: str) -> list[float] | None:
    if bbox_match := re.search(BBOX_PATTERN, text):
        bbox_text = bbox_match.groupdict()["coordinates"]
        return [float(n) for n in bbox_text.split(",")]
    return None


def intersect(bbox1: list[float], bbox2: list[float]) -> bool:
    bbox1_polygon = geometry.box(*bbox1, ccw=True)
    bbox2_polygon = geometry.box(*bbox2, ccw=True)
    return bbox1_polygon.intersects(bbox2_polygon)
