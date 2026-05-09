"""Shift business logic."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Shift, Site, User


class ShiftAlreadyOpenError(Exception):
    pass


class NoOpenShiftError(Exception):
    pass


async def ensure_user(session: AsyncSession, tg_id: int, name: str) -> User:
    stmt = select(User).where(User.tg_id == tg_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, name=name)
        session.add(user)
        await session.flush()
    return user


async def get_open_shift(session: AsyncSession, user_id: int) -> Shift | None:
    stmt = select(Shift).where(Shift.user_id == user_id, Shift.end_at.is_(None))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def start_shift(
    session: AsyncSession,
    user_id: int,
    site_id: int | None,
    location_wkt: str | None = None,
) -> Shift:
    from geoalchemy2.elements import WKTElement

    shift = Shift(
        user_id=user_id,
        site_id=site_id,
        start_at=datetime.now(tz=ZoneInfo("UTC")),
        start_location=WKTElement(location_wkt, srid=4326) if location_wkt else None,
    )
    session.add(shift)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ShiftAlreadyOpenError() from exc
    return shift


async def stop_shift(
    session: AsyncSession,
    shift: Shift,
    location_wkt: str | None = None,
) -> Shift:
    from geoalchemy2.elements import WKTElement

    shift.end_at = datetime.now(tz=ZoneInfo("UTC"))
    if location_wkt:
        shift.end_location = WKTElement(location_wkt, srid=4326)
    await session.flush()
    return shift


async def get_user_sites(session: AsyncSession, user_id: int) -> list[Site]:
    stmt = select(Site).where(Site.user_id == user_id, Site.archived_at.is_(None))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_site(session: AsyncSession, user_id: int, name: str) -> Site:
    site = Site(user_id=user_id, name=name)
    session.add(site)
    await session.flush()
    return site
