from shapely import geometry


def bbox2polygon(bbox: list[float]) -> geometry.Polygon:
    return geometry.box(*bbox, ccw=True)
