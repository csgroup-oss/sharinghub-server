from shapely import errors, wkt
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry


def bbox2geom(bbox: list[float]) -> BaseGeometry | None:
    try:
        return box(*bbox, ccw=True)
    except (ValueError, TypeError):
        return None


def geojson2geom(geojson: dict) -> BaseGeometry | None:
    try:
        return shape(geojson)
    except (AttributeError, errors.GeometryTypeError):
        return None


def wkt2geom(wkt_data: str) -> BaseGeometry | None:
    try:
        return wkt.loads(wkt_data)
    except (TypeError, errors.GEOSException):
        return None


def get_geojson_geometry(geometry: BaseGeometry) -> dict:
    return mapping(geometry)
