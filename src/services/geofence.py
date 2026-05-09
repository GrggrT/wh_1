"""Geofence (point-in-polygon) checks using PostGIS."""

from sqlalchemy import func, select
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
