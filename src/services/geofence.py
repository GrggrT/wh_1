"""Geofence (point-in-polygon) checks using PostGIS."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Site


async def check_point_in_site(
    session: AsyncSession, site_id: int, lon: float, lat: float
) -> bool | None:
    """Check if a point is within the site polygon.

    Returns:
        True if inside, False if outside, None if site has no polygon.
    Edge points are treated as INSIDE (ST_Covers is inclusive of boundary).
    """
    stmt = select(Site.polygon).where(Site.id == site_id)
    result = await session.execute(stmt)
    polygon = result.scalar_one_or_none()

    if polygon is None:
        return None

    point_wkt = f"SRID=4326;POINT({lon} {lat})"
    check_stmt = select(
        func.ST_Covers(
            Site.polygon,
            func.ST_GeogFromText(point_wkt),
        )
    ).where(Site.id == site_id)
    check_result = await session.execute(check_stmt)
    result_val: bool | None = check_result.scalar_one_or_none()
    return result_val


def build_polygon_wkt(points: list[tuple[float, float]]) -> str:
    """Build a closed POLYGON WKT (lon lat) from at least 3 points.

    Auto-closes the ring by appending the first point if not already closed.
    """
    if len(points) < 3:
        raise ValueError("polygon requires at least 3 points")
    ring = list(points)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    coords = ", ".join(f"{lon} {lat}" for lon, lat in ring)
    return f"SRID=4326;POLYGON(({coords}))"


async def set_site_polygon(
    session: AsyncSession, site_id: int, points: list[tuple[float, float]],
) -> None:
    """Persist a polygon geometry for the given site from a list of (lon, lat)."""
    wkt = build_polygon_wkt(points)
    await session.execute(
        update(Site)
        .where(Site.id == site_id)
        .values(polygon=func.ST_GeogFromText(wkt)),
    )


async def clear_site_polygon(session: AsyncSession, site_id: int) -> None:
    await session.execute(
        update(Site).where(Site.id == site_id).values(polygon=None),
    )
