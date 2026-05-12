"""System-info commands: /whoami, /status, /crew_open."""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select, text

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import AuditLog, Crew, Shift, Site, User
from src.services.audit import write_audit
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    get_crew_for_foreman,
    list_crew_members,
)
from src.services.digest import (
    build_daily_digest,
    build_global_stats,
    build_monthly_digest,
    build_site_breakdown,
    build_weekly_digest,
    build_work_type_breakdown,
    previous_full_week,
    previous_month,
)
from src.services.reports import compute_hours
from src.services.shifts import get_open_shift

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
    rate = (
        "—"
        if db_user.hourly_rate is None
        else f"{db_user.hourly_rate} {db_user.currency}/ч"
    )
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


@router.message(Command("digest"))
async def cmd_digest(message: Message, db_user: User | None = None) -> None:
    """Owner: show today's digest on demand."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    body = ""
    async for session in get_session():
        body = await build_daily_digest(session, tz)
    await message.answer(body)


@router.message(Command("digest_week"))
async def cmd_digest_week(message: Message, db_user: User | None = None) -> None:
    """Owner: weekly digest for the previous full Monday..Sunday week."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    today_local = datetime.now(tz=tz).date()
    week_start, week_end = previous_full_week(today_local)
    body = ""
    async for session in get_session():
        body = await build_weekly_digest(session, tz, week_start, week_end)
    await message.answer(body)


_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


@router.message(Command("digest_month"))
async def cmd_digest_month(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner: monthly digest. Defaults to previous month if no arg."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    if command.args:
        match = _PERIOD_RE.match(command.args.strip())
        if match is None:
            await message.answer(t("digest_month_usage"))
            return
        year, month = int(match.group(1)), int(match.group(2))
        if not (1 <= month <= 12):
            await message.answer(t("digest_month_usage"))
            return
    else:
        today = date.today()
        year, month = previous_month(today.year, today.month)
    body = ""
    async for session in get_session():
        body = await build_monthly_digest(session, tz, year, month)
    await message.answer(body)


def _parse_month_arg(raw: str | None, today: date) -> tuple[int, int] | None:
    """Parse YYYY-MM, default to current local month if raw is None/empty."""
    if not raw:
        return today.year, today.month
    match = _PERIOD_RE.match(raw.strip())
    if match is None:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return year, month


@router.message(Command("work_stats"))
async def cmd_work_stats(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner: month breakdown by work_type. Defaults to current month."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    parsed = _parse_month_arg(command.args, datetime.now(tz=tz).date())
    if parsed is None:
        await message.answer(t("work_stats_usage"))
        return
    year, month = parsed
    body = ""
    async for session in get_session():
        body = await build_work_type_breakdown(session, tz, year, month)
    await message.answer(body)


@router.message(Command("site_stats"))
async def cmd_site_stats(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner: month breakdown by site. Defaults to current month."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    parsed = _parse_month_arg(command.args, datetime.now(tz=tz).date())
    if parsed is None:
        await message.answer(t("site_stats_usage"))
        return
    year, month = parsed
    body = ""
    async for session in get_session():
        body = await build_site_breakdown(session, tz, year, month)
    await message.answer(body)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db_user: User | None = None) -> None:
    """Owner: all-time + month-to-date totals across every user."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    body = ""
    async for session in get_session():
        body = await build_global_stats(session, tz)
    await message.answer(body)


@router.message(Command("admin_audit"))
async def cmd_admin_audit(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner: last N audit_log rows where entity_type != 'shift'. Default N=20."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    limit = 20
    if command.args:
        try:
            limit = max(1, min(100, int(command.args.strip())))
        except ValueError:
            await message.answer(t("admin_audit_usage"))
            return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    lines: list[str] = []
    async for session in get_session():
        rows = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type != "shift")
                    .order_by(AuditLog.created_at.desc())
                    .limit(limit),
                )
            ).scalars().all(),
        )
        if not rows:
            await message.answer(t("admin_audit_empty"))
            return
        actor_ids = {r.user_id for r in rows}
        actors_res = await session.execute(
            select(User).where(User.id.in_(actor_ids)),
        )
        actors_map = {u.id: u.name for u in actors_res.scalars().all()}
        for r in rows:
            local_dt = r.created_at.astimezone(tz)
            actor = actors_map.get(r.user_id, f"id={r.user_id}")
            lines.append(
                f"{local_dt.strftime('%d.%m %H:%M')} {actor} "
                f"{r.action} {r.entity_type}#{r.entity_id}",
            )
    await message.answer(t("admin_audit_list", body="\n".join(lines)))


@router.message(Command("active"))
async def cmd_active(message: Message, db_user: User | None = None) -> None:
    """Owner: list every currently open shift across all crews/users."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz=ZoneInfo("UTC"))
    lines: list[str] = []
    async for session in get_session():
        open_stmt = (
            select(Shift)
            .where(Shift.end_at.is_(None))
            .order_by(Shift.start_at)
        )
        open_shifts = list((await session.execute(open_stmt)).scalars().all())
        if not open_shifts:
            await message.answer(t("active_none"))
            return
        user_ids = {s.user_id for s in open_shifts}
        users = (await session.execute(
            select(User).where(User.id.in_(user_ids)),
        )).scalars().all()
        users_map = {u.id: u for u in users}
        site_ids = {s.site_id for s in open_shifts if s.site_id}
        sites: dict[int, Site] = {}
        if site_ids:
            site_res = await session.execute(
                select(Site).where(Site.id.in_(site_ids)),
            )
            sites = {s.id: s for s in site_res.scalars().all()}
        for shift in open_shifts:
            user_obj = users_map.get(shift.user_id)
            site_name = (
                sites[shift.site_id].name
                if shift.site_id and shift.site_id in sites
                else "—"
            )
            elapsed = compute_hours(shift.start_at, now).quantize(Decimal("0.1"))
            local_start = shift.start_at.astimezone(tz).strftime("%m-%d %H:%M")
            name = user_obj.name if user_obj else f"#{shift.user_id}"
            lines.append(
                f"• {name} — «{site_name}», с {local_start} ({elapsed} ч)",
            )
    await message.answer(t("active_summary", body="\n".join(lines)))


@router.message(Command("my_open"))
async def cmd_my_open(message: Message, db_user: User | None = None) -> None:
    """Show the caller's currently-open shift, if any."""
    if db_user is None:
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    now = datetime.now(tz=ZoneInfo("UTC"))
    body = ""
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("my_open_none"))
            return
        site_name = "—"
        if shift.site_id is not None:
            site_obj = (
                await session.execute(
                    select(Site).where(Site.id == shift.site_id),
                )
            ).scalar_one_or_none()
            if site_obj is not None:
                site_name = site_obj.name
        elapsed = compute_hours(shift.start_at, now).quantize(Decimal("0.1"))
        local_start = shift.start_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        body = t(
            "my_open_body",
            id=str(shift.id),
            site=site_name,
            start=local_start,
            hours=str(elapsed),
        )
    await message.answer(body)


@router.message(Command("leave_crew"))
async def cmd_leave_crew(message: Message, db_user: User | None = None) -> None:
    """Worker self-detach from their crew. Refuses if open shift exists."""
    if db_user is None:
        return
    if db_user.role == ROLE_OWNER:
        await message.answer(t("leave_crew_owner"))
        return
    if db_user.role == ROLE_FOREMAN:
        await message.answer(t("leave_crew_foreman"))
        return
    if db_user.crew_id is None:
        await message.answer(t("leave_crew_not_in"))
        return
    async for session in get_session():
        open_shift = await get_open_shift(session, db_user.id)
        if open_shift is not None:
            await message.answer(t("leave_crew_open_shift"))
            return
        # Reload user from this session to mutate persistently.
        user_in_session = (
            await session.execute(select(User).where(User.id == db_user.id))
        ).scalar_one()
        old_crew_id = user_in_session.crew_id
        user_in_session.crew_id = None
        await write_audit(
            session,
            actor_id=db_user.id,
            entity_type="user",
            entity_id=db_user.id,
            action="leave_crew",
            diff={"crew_id": {"before": old_crew_id, "after": None}},
        )
        await session.commit()
    await message.answer(t("leave_crew_done"))


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
