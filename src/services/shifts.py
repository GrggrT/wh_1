"""Shift business logic."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Crew, Shift, Site, User
from src.services.crews import ROLE_FOREMAN, ROLE_OWNER


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


async def get_last_site_id(session: AsyncSession, user_id: int) -> int | None:
    """Most-recently used site_id from this user's prior shifts (any state)."""
    stmt = (
        select(Shift.site_id)
        .where(Shift.user_id == user_id, Shift.site_id.is_not(None))
        .order_by(Shift.start_at.desc())
        .limit(1)
    )
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


async def resolve_effective_site_owner_id(
    session: AsyncSession, db_user: User,
) -> int | None:
    """Resolve which user_id owns the sites this user is allowed to clock in to.

    - owner: own sites
    - foreman: own sites (foreman is the user_id of their crew's sites)
    - worker with crew_id: sites of that crew's foreman_user_id
    - worker without a crew: None (no visible sites)
    """
    if db_user.role == ROLE_OWNER or db_user.role == ROLE_FOREMAN:
        return db_user.id
    if db_user.crew_id is None:
        return None
    crew = (
        await session.execute(select(Crew).where(Crew.id == db_user.crew_id))
    ).scalar_one_or_none()
    return crew.foreman_user_id if crew is not None else None


async def get_visible_sites_for_user(
    session: AsyncSession, db_user: User,
) -> list[Site]:
    """Active sites this user can clock in to. Empty list if no effective owner."""
    owner_id = await resolve_effective_site_owner_id(session, db_user)
    if owner_id is None:
        return []
    stmt = (
        select(Site)
        .where(Site.user_id == owner_id, Site.archived_at.is_(None))
        .order_by(Site.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_site(session: AsyncSession, user_id: int, name: str) -> Site:
    site = Site(user_id=user_id, name=name)
    session.add(site)
    await session.flush()
    return site
