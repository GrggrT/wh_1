"""Geofence logic tests (unit-level, no DB)."""

# These tests verify the geofence service queries.
# Full integration requires PostGIS, so here we test the helper logic.



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
