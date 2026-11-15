import math

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, shape
from sqlalchemy import cast, func, select

SRID = 4326


def point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=SRID)


def latlng(geom) -> tuple[float, float]:
    p = to_shape(geom)
    return p.y, p.x


def from_geojson(geom: dict) -> WKTElement:
    return WKTElement(shape(geom).wkt, srid=SRID)


def to_geojson(geom) -> dict:
    return mapping(to_shape(geom))


def pt_expr(lat: float, lng: float):
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), SRID)


def within_m(col, lat: float, lng: float, metres):
    """SQL: column is within `metres` of the point (geography, so metres are real)."""
    return func.ST_DWithin(cast(col, Geography), cast(pt_expr(lat, lng), Geography), metres)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def assign_ward(db, lat: float, lng: float) -> str | None:
    from .models import Ward

    return db.scalar(select(Ward.name).where(func.ST_Contains(Ward.boundary, pt_expr(lat, lng))).limit(1))
