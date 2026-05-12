"""Owner/foreman admin: rates and site management."""

import contextlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Shift, Site, User
from src.services.audit import write_audit
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
    target_currency = db_user.currency
    notify_tg_id: int | None = None
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
        old_rate = str(target.hourly_rate) if target.hourly_rate is not None else None
        target.hourly_rate = rate
        target_name = target.name
        target_currency = target.currency
        if target.id != db_user.id:
            notify_tg_id = target.tg_id
        await write_audit(
            session, db_user.id, "user", target.id, "rate_change",
            {"hourly_rate": {"before": old_rate, "after": str(rate)}},
        )
        await session.commit()
    await message.answer(
        t("rate_set", name=target_name, rate=str(rate), currency=target_currency),
    )
    if notify_tg_id is not None and message.bot is not None:
        with contextlib.suppress(TelegramAPIError):
            await message.bot.send_message(
                notify_tg_id,
                t(
                    "rate_changed_notify",
                    rate=str(rate),
                    currency=target_currency,
                ),
            )


@router.message(Command("my_rate"))
async def cmd_my_rate(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    if db_user.hourly_rate is None:
        await message.answer(t("rate_not_set"))
    else:
        await message.answer(
            t("my_rate", rate=str(db_user.hourly_rate), currency=db_user.currency),
        )


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
    """List sites visible to the user.

    Owner/foreman: their own (manageable) sites, including archived.
    Worker in a crew: read-only view of crew's active sites.
    """
    if db_user is None:
        await message.answer(t("not_authorized"))
        return
    is_admin = db_user.role in (ROLE_OWNER, ROLE_FOREMAN)
    async for session in get_session():
        from src.services.shifts import resolve_effective_site_owner_id

        owner_id = await resolve_effective_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        stmt = select(Site).where(Site.user_id == owner_id)
        if not is_admin:
            stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.order_by(Site.name)
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
        old_rate = str(site.hourly_rate) if site.hourly_rate is not None else None
        site.hourly_rate = rate
        site_name = site.name
        await write_audit(
            session, db_user.id, "site", site.id, "rate_change",
            {"hourly_rate": {"before": old_rate, "after": str(rate)}},
        )
        await session.commit()
    await message.answer(
        t("site_rate_set", name=site_name, rate=str(rate), currency=db_user.currency),
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
        was_archived = site.archived_at is not None
        if site.archived_at is None:
            site.archived_at = datetime.now(tz=UTC)
        site_name = site.name
        if not was_archived:
            await write_audit(
                session, db_user.id, "site", site.id, "archive",
                {"archived_at": {"before": None, "after": site.archived_at.isoformat()}},
            )
        await session.commit()
    await message.answer(t("site_archived", name=site_name))


@router.message(Command("unarchive_site"))
async def cmd_unarchive_site(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("unarchive_site_usage"))
        return
    try:
        site_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("unarchive_site_usage"))
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
        prev_archived = (
            site.archived_at.isoformat() if site.archived_at is not None else None
        )
        site.archived_at = None
        site_name = site.name
        await write_audit(
            session, db_user.id, "site", site.id, "unarchive",
            {"archived_at": {"before": prev_archived, "after": None}},
        )
        await session.commit()
    await message.answer(t("site_unarchived", name=site_name))


@router.message(Command("rename_site"))
async def cmd_rename_site(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner/foreman: /rename_site <site_id> <new name>."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("rename_site_usage"))
        return
    parts = command.args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(t("rename_site_usage"))
        return
    try:
        site_id = int(parts[0])
    except ValueError:
        await message.answer(t("rename_site_usage"))
        return
    new_name = parts[1].strip()
    if not new_name:
        await message.answer(t("rename_site_usage"))
        return
    old_name = ""
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
        old_name = site.name
        site.name = new_name
        await write_audit(
            session, db_user.id, "site", site.id, "rename",
            {"name": {"before": old_name, "after": new_name}},
        )
        await session.commit()
    await message.answer(t("site_renamed", old=old_name, new=new_name))


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
    notify_tg_ids: list[int] = []
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        old_default = (
            str(crew.default_hourly_rate) if crew.default_hourly_rate is not None else None
        )
        await set_crew_default_rate(session, crew, rate)
        crew_name = crew.name
        await write_audit(
            session, db_user.id, "crew", crew.id, "default_rate_change",
            {"default_hourly_rate": {"before": old_default, "after": str(rate)}},
        )
        members_using_default = list(
            (
                await session.execute(
                    select(User).where(
                        User.crew_id == crew.id, User.hourly_rate.is_(None),
                    ),
                )
            ).scalars().all(),
        )
        notify_tg_ids = [m.tg_id for m in members_using_default if m.id != db_user.id]
        await session.commit()
    await message.answer(
        t(
            "crew_rate_set",
            crew=crew_name,
            rate=str(rate),
            currency=db_user.currency,
        ),
    )
    if notify_tg_ids and message.bot is not None:
        for tg_id in notify_tg_ids:
            with contextlib.suppress(TelegramAPIError):
                await message.bot.send_message(
                    tg_id,
                    t(
                        "crew_rate_changed_notify",
                        rate=str(rate),
                        currency=db_user.currency,
                    ),
                )


@router.message(Command("site_info"))
async def cmd_site_info(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner/foreman: detailed view of one site they manage."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("site_info_usage"))
        return
    try:
        site_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("site_info_usage"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    body = ""
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
        rate = (
            f"{site.hourly_rate} zł/ч" if site.hourly_rate is not None else "—"
        )
        archived_str = "—"
        if site.archived_at is not None:
            archived_str = site.archived_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        polygon_str = "да" if site.polygon is not None else "нет"
        cutoff = datetime.now(tz=UTC) - timedelta(days=30)
        shift_count = (
            await session.execute(
                select(func.count(Shift.id)).where(
                    Shift.site_id == site.id, Shift.start_at >= cutoff,
                ),
            )
        ).scalar_one()
        body = t(
            "site_info_body",
            id=str(site.id),
            name=site.name,
            rate=rate,
            archived=archived_str,
            polygon=polygon_str,
            shifts_30d=str(shift_count),
        )
    await message.answer(body)


@router.message(Command("sites_archive"))
async def cmd_sites_archive(message: Message, db_user: User | None = None) -> None:
    """Owner/foreman: list only archived sites in their scope."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    lines: list[str] = []
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        stmt = (
            select(Site)
            .where(Site.user_id == owner_id, Site.archived_at.is_not(None))
            .order_by(Site.archived_at.desc())
        )
        sites = list((await session.execute(stmt)).scalars().all())
        if not sites:
            await message.answer(t("sites_archive_empty"))
            return
        for site in sites:
            assert site.archived_at is not None
            local = site.archived_at.astimezone(tz).strftime("%Y-%m-%d")
            lines.append(f"• #{site.id} {site.name} — архив с {local}")
    await message.answer(t("sites_archive_list", body="\n".join(lines)))


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
