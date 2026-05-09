"""Roles, crews, and invite-code helpers."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Crew, InviteCode, User

ROLE_OWNER = "owner"
ROLE_FOREMAN = "foreman"
ROLE_WORKER = "worker"

_UTC = ZoneInfo("UTC")
_INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
INVITE_CODE_LENGTH = 6
INVITE_TTL_HOURS = 72


class InviteError(Exception):
    pass


class CrewError(Exception):
    pass


def generate_invite_code() -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


async def ensure_owner_role(session: AsyncSession, owner_tg_id: int) -> User | None:
    """Promote the user matching owner_tg_id to role='owner' if found."""
    stmt = select(User).where(User.tg_id == owner_tg_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None and user.role != ROLE_OWNER:
        user.role = ROLE_OWNER
        await session.flush()
    return user


async def promote_to_foreman(
    session: AsyncSession,
    target_tg_id: int,
    crew_name: str,
) -> Crew:
    """Promote the target user to foreman and create their crew."""
    stmt = select(User).where(User.tg_id == target_tg_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise CrewError("user_not_found")
    user.role = ROLE_FOREMAN
    crew = Crew(foreman_user_id=user.id, name=crew_name)
    session.add(crew)
    await session.flush()
    user.crew_id = crew.id
    await session.flush()
    return crew


async def get_crew_for_foreman(
    session: AsyncSession, foreman_user_id: int,
) -> Crew | None:
    stmt = select(Crew).where(Crew.foreman_user_id == foreman_user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_crew_members(
    session: AsyncSession, crew_id: int,
) -> list[User]:
    stmt = select(User).where(User.crew_id == crew_id).order_by(User.name)
    return list((await session.execute(stmt)).scalars().all())


async def list_foremen(session: AsyncSession) -> list[User]:
    stmt = select(User).where(User.role == ROLE_FOREMAN).order_by(User.name)
    return list((await session.execute(stmt)).scalars().all())


async def issue_invite_code(
    session: AsyncSession,
    crew_id: int,
    created_by_user_id: int,
    now: datetime | None = None,
) -> InviteCode:
    current = now or datetime.now(tz=_UTC)
    for _ in range(8):
        code = generate_invite_code()
        existing = (
            await session.execute(select(InviteCode).where(InviteCode.code == code))
        ).scalar_one_or_none()
        if existing is None:
            break
    else:
        raise InviteError("collision")
    invite = InviteCode(
        code=code,
        crew_id=crew_id,
        created_by_user_id=created_by_user_id,
        expires_at=current + timedelta(hours=INVITE_TTL_HOURS),
    )
    session.add(invite)
    await session.flush()
    return invite


async def redeem_invite_code(
    session: AsyncSession,
    code: str,
    user: User,
    now: datetime | None = None,
) -> Crew:
    current = now or datetime.now(tz=_UTC)
    stmt = select(InviteCode).where(InviteCode.code == code)
    invite = (await session.execute(stmt)).scalar_one_or_none()
    if invite is None:
        raise InviteError("not_found")
    if invite.used_at is not None:
        raise InviteError("already_used")
    if invite.expires_at <= current:
        raise InviteError("expired")
    crew = (
        await session.execute(select(Crew).where(Crew.id == invite.crew_id))
    ).scalar_one_or_none()
    if crew is None:
        raise InviteError("crew_missing")
    invite.used_at = current
    invite.used_by_user_id = user.id
    user.crew_id = crew.id
    if user.role == ROLE_OWNER:
        # Owner stays owner; do not downgrade.
        pass
    elif user.role != ROLE_FOREMAN:
        user.role = ROLE_WORKER
    # Apply crew default rate to a joiner who has none of their own.
    if user.hourly_rate is None and crew.default_hourly_rate is not None:
        user.hourly_rate = crew.default_hourly_rate
    await session.flush()
    return crew


async def set_crew_default_rate(
    session: AsyncSession, crew: Crew, rate: Decimal,
) -> Crew:
    crew.default_hourly_rate = rate
    await session.flush()
    return crew
