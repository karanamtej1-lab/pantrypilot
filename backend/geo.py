"""Distance math and ZIP code lookup."""

import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

EARTH_RADIUS_MILES = 3958.8

ZIP_CENTROIDS_PATH = Path(__file__).resolve().parent.parent / "data" / "zip_centroids.json"


def haversine_miles(lat1, lng1, lat2, lng2):
    """Straight-line ("as the crow flies") distance in miles between two points.

    The Earth is a sphere, so we can't use the flat Pythagorean formula.
    Haversine measures the arc along the Earth's surface instead.
    """
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    d_lat = lat2 - lat1
    d_lng = lng2 - lng1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))


def load_zip_centroids():
    """{"75070": {"lat": ..., "lng": ...}, ...}. Empty if the file hasn't been built yet."""
    if not ZIP_CENTROIDS_PATH.exists():
        return {}
    with open(ZIP_CENTROIDS_PATH, encoding="utf-8") as f:
        return json.load(f)
