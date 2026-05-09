"""Owner/foreman admin: rates and site management."""

from decimal import Decimal, InvalidOperation

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import Site, User
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    get_crew_for_foreman,
    list_crew_members,
    set_crew_default_rate,
)

router = Router()


def _parse_rate(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return value.quantize(Decimal("0.01"))


# --- RATES ---


@router.message(Command("set_rate"))
async def cmd_set_rate(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Set hourly rate for a worker. Owner: any user; foreman: own crew only."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("set_rate_usage"))
        return
    parts = command.args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(t("set_rate_usage"))
        return
    try:
        target_tg_id = int(parts[0])
    except ValueError:
        await message.answer(t("set_rate_usage"))
        return
    rate = _parse_rate(parts[1])
    if rate is None:
        await message.answer(t("rate_invalid"))
        return
    target_name = ""
    async for session in get_session():
        target = (
            await session.execute(select(User).where(User.tg_id == target_tg_id))
        ).scalar_one_or_none()
        if target is None:
            await message.answer(t("user_not_seen"))
            return
        if db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None or target.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        target.hourly_rate = rate
        target_name = target.name
        await session.commit()
    await message.answer(t("rate_set", name=target_name, rate=str(rate)))


@router.message(Command("my_rate"))
async def cmd_my_rate(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    if db_user.hourly_rate is None:
        await message.answer(t("rate_not_set"))
    else:
        await message.answer(t("my_rate", rate=str(db_user.hourly_rate)))


# --- SITES ---


async def _resolve_site_owner_id(
    session: AsyncSession,
    db_user: User,
) -> int | None:
    """Determine which user 'owns' the sites for this admin.

    Owner manages their own sites; a foreman manages the sites of their crew's
    foreman record (i.e. the foreman_user_id on their Crew).
    """
    if db_user.role == ROLE_OWNER:
        return db_user.id
    if db_user.role == ROLE_FOREMAN:
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            return None
        return crew.foreman_user_id
    return None


@router.message(Command("sites"))
async def cmd_sites(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        stmt = select(Site).where(Site.user_id == owner_id).order_by(Site.name)
        sites = list((await session.execute(stmt)).scalars().all())
    if not sites:
        await message.answer(t("sites_empty"))
        return
    lines: list[str] = []
    for site in sites:
        rate = (
            f"{site.hourly_rate} zł/ч" if site.hourly_rate is not None else "—"
        )
        archived = " (архив)" if site.archived_at is not None else ""
        lines.append(f"• #{site.id} {site.name}{archived} — {rate}")
    await message.answer(t("sites_list", body="\n".join(lines)))


@router.message(Command("set_site_rate"))
async def cmd_set_site_rate(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("set_site_rate_usage"))
        return
    parts = command.args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(t("set_site_rate_usage"))
        return
    try:
        site_id = int(parts[0])
    except ValueError:
        await message.answer(t("set_site_rate_usage"))
        return
    rate = _parse_rate(parts[1])
    if rate is None:
        await message.answer(t("rate_invalid"))
        return
    site_name = ""
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        site = (
            await session.execute(select(Site).where(Site.id == site_id))
        ).scalar_one_or_none()
        if site is None or site.user_id != owner_id:
            await message.answer(t("site_not_found"))
            return
        site.hourly_rate = rate
        site_name = site.name
        await session.commit()
    await message.answer(
        t("site_rate_set", name=site_name, rate=str(rate)),
    )


@router.message(Command("archive_site"))
async def cmd_archive_site(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    from datetime import UTC, datetime

    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("archive_site_usage"))
        return
    try:
        site_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("archive_site_usage"))
        return
    site_name = ""
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        site = (
            await session.execute(select(Site).where(Site.id == site_id))
        ).scalar_one_or_none()
        if site is None or site.user_id != owner_id:
            await message.answer(t("site_not_found"))
            return
        if site.archived_at is None:
            site.archived_at = datetime.now(tz=UTC)
        site_name = site.name
        await session.commit()
    await message.answer(t("site_archived", name=site_name))


@router.message(Command("set_crew_rate"))
async def cmd_set_crew_rate(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Foreman/owner: set the crew default hourly rate for new joiners."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("set_crew_rate_usage"))
        return
    rate = _parse_rate(command.args.strip())
    if rate is None:
        await message.answer(t("rate_invalid"))
        return
    crew_name = ""
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        await set_crew_default_rate(session, crew, rate)
        crew_name = crew.name
        await session.commit()
    await message.answer(
        t("crew_rate_set", crew=crew_name, rate=str(rate)),
    )


@router.message(Command("crew_rates"))
async def cmd_crew_rates(message: Message, db_user: User | None = None) -> None:
    """Foreman/owner: see hourly rates of every crew member."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        members = await list_crew_members(session, crew.id)
        crew_name = crew.name
    if not members:
        await message.answer(t("crew_empty", crew=crew_name))
        return
    lines = [
        f"• {m.name} (tg_id={m.tg_id}) — "
        f"{m.hourly_rate if m.hourly_rate is not None else '—'} zł/ч"
        for m in members
    ]
    await message.answer(t("crew_rates_list", crew=crew_name, body="\n".join(lines)))
