from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry, GeometryTypeError


def bbox2geom(bbox: list[float]) -> BaseGeometry | None:
    try:
        return box(*bbox, ccw=True)
    except (ValueError, TypeError):
        return None


def geojson2geom(geojson: dict) -> BaseGeometry | None:
    try:
        return shape(geojson)
    except (AttributeError, GeometryTypeError):
        return None
