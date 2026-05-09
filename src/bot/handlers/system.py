"""System-info commands: /whoami, /status, /crew_open."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, text

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Crew, Shift, Site, User
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    get_crew_for_foreman,
    list_crew_members,
)
from src.services.reports import compute_hours

router = Router()

# Module-level start timestamp for /status uptime
_STARTED_AT = datetime.now(tz=UTC)


@router.message(Command("whoami"))
async def cmd_whoami(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    crew_name: str | None = None
    if db_user.crew_id is not None:
        async for session in get_session():
            crew = (
                await session.execute(
                    select(Crew).where(Crew.id == db_user.crew_id),
                )
            ).scalar_one_or_none()
            if crew is not None:
                crew_name = crew.name
    rate = "—" if db_user.hourly_rate is None else f"{db_user.hourly_rate} zł/ч"
    await message.answer(
        t(
            "whoami",
            name=db_user.name,
            tg_id=str(db_user.tg_id),
            role=db_user.role,
            crew=crew_name or "—",
            rate=rate,
        ),
    )


@router.message(Command("status"))
async def cmd_status(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    now = datetime.now(tz=UTC)
    uptime = now - _STARTED_AT
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}ч {minutes}м {seconds}с"

    db_ok = "OK"
    try:
        async for session in get_session():
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = "FAIL"

    await message.answer(
        t(
            "status",
            uptime=uptime_str,
            db=db_ok,
            started=_STARTED_AT.strftime("%Y-%m-%d %H:%M UTC"),
        ),
    )


@router.message(Command("crew_open"))
async def cmd_crew_open(message: Message, db_user: User | None = None) -> None:
    """Show foreman who in their crew is currently clocked in."""
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz=ZoneInfo("UTC"))

    lines: list[str] = []
    crew_name = ""
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        crew_name = crew.name
        members = await list_crew_members(session, crew.id)
        if not members:
            await message.answer(t("crew_empty", crew=crew_name))
            return
        member_ids = [m.id for m in members]
        stmt = (
            select(Shift)
            .where(Shift.user_id.in_(member_ids), Shift.end_at.is_(None))
            .order_by(Shift.start_at)
        )
        open_shifts = list((await session.execute(stmt)).scalars().all())
        if not open_shifts:
            await message.answer(t("crew_open_none", crew=crew_name))
            return

        site_ids = {s.site_id for s in open_shifts if s.site_id}
        sites: dict[int, Site] = {}
        if site_ids:
            site_res = await session.execute(
                select(Site).where(Site.id.in_(site_ids)),
            )
            sites = {s.id: s for s in site_res.scalars().all()}
        member_by_id = {m.id: m for m in members}

        for shift in open_shifts:
            member = member_by_id[shift.user_id]
            site_name = (
                sites[shift.site_id].name
                if shift.site_id and shift.site_id in sites
                else "—"
            )
            elapsed = compute_hours(shift.start_at, now).quantize(Decimal("0.1"))
            local_start = shift.start_at.astimezone(tz).strftime("%H:%M")
            lines.append(
                t(
                    "crew_open_row",
                    name=member.name,
                    site=site_name,
                    start=local_start,
                    hours=str(elapsed),
                ),
            )

    await message.answer(t("crew_open_summary", crew=crew_name, body="\n".join(lines)))
