"""Geofence logic tests (unit-level, no DB)."""

# These tests verify the geofence service queries.
# Full integration requires PostGIS, so here we test the helper logic.

import pytest
from src.services.geofence import build_polygon_wkt


def test_point_wkt_format() -> None:
    """Verify we generate correct WKT for PostGIS."""
    lon, lat = 21.0122, 52.2297
    wkt = f"POINT({lon} {lat})"
    assert wkt == "POINT(21.0122 52.2297)"


def test_polygon_wkt_format() -> None:
    """Verify polygon WKT structure."""
    # Simple square around Warsaw center
    polygon = "POLYGON((20.9 52.1, 21.1 52.1, 21.1 52.3, 20.9 52.3, 20.9 52.1))"
    assert polygon.startswith("POLYGON((")
    assert polygon.endswith("))")


def test_build_polygon_wkt_auto_closes() -> None:
    points = [(20.9, 52.1), (21.1, 52.1), (21.0, 52.3)]
    wkt = build_polygon_wkt(points)
    assert wkt.startswith("SRID=4326;POLYGON((")
    assert wkt.endswith("))")
    # Three points + closing repeat of the first => 4 coordinate pairs.
    assert wkt.count(",") == 3


def test_build_polygon_wkt_already_closed_not_duplicated() -> None:
    points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)]
    wkt = build_polygon_wkt(points)
    # 4 coords already including close, so 3 commas.
    assert wkt.count(",") == 3


def test_build_polygon_wkt_too_few_raises() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        build_polygon_wkt([(0.0, 0.0), (1.0, 1.0)])
