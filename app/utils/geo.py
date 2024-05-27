# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
