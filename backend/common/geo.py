"""Distance helpers without PostGIS (great-circle distance computed in SQL)."""

import math

from django.db.models import F, FloatField, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import ACos, Cos, Least, Radians, Sin

EARTH_RADIUS_KM = 6371.0


def distance_km_expression(lat: float, lng: float, lat_field: str, lng_field: str):
    """Distance in km between a point and a pair of model fields, as an ORM expression.

    Uses the spherical law of cosines. `Least(1.0, ...)` guards ACOS against floating
    point values marginally above 1 when both points are identical.
    """
    lat_r = Radians(Value(float(lat)))
    lng_r = Radians(Value(float(lng)))
    field_lat = Radians(F(lat_field))
    field_lng = Radians(F(lng_field))
    cosine = ExpressionWrapper(
        Cos(lat_r) * Cos(field_lat) * Cos(field_lng - lng_r) + Sin(lat_r) * Sin(field_lat),
        output_field=FloatField(),
    )
    return ExpressionWrapper(
        Value(EARTH_RADIUS_KM) * ACos(Least(Value(1.0), cosine)), output_field=FloatField()
    )


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Index-friendly prefilter: (min_lat, max_lat, min_lng, max_lng)."""
    dlat = radius_km / 111.0
    dlng = radius_km / max(111.0 * math.cos(math.radians(lat)), 0.0001)
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng
