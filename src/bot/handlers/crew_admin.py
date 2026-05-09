"""Owner and foreman commands: manage foremen, crews, and invite codes."""

import re
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Shift, Site, User
from src.exporters.xlsx import export_crew_xlsx
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    CrewError,
    InviteError,
    get_crew_for_foreman,
    issue_invite_code,
    list_crew_members,
    list_foremen,
    promote_to_foreman,
    redeem_invite_code,
)
from src.services.reports import (
    compute_period_hours,
    get_shifts_for_users_in_period,
)

router = Router()


# --- OWNER ---


@router.message(Command("add_foreman"))
async def cmd_add_foreman(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("add_foreman_usage"))
        return
    parts = command.args.split(maxsplit=1)
    try:
        target_tg_id = int(parts[0])
    except ValueError:
        await message.answer(t("add_foreman_usage"))
        return
    crew_name = parts[1].strip() if len(parts) > 1 else f"Бригада {target_tg_id}"
    async for session in get_session():
        try:
            crew = await promote_to_foreman(session, target_tg_id, crew_name)
        except CrewError:
            await message.answer(t("user_not_seen"))
            return
        await session.commit()
    await message.answer(t("foreman_added", crew=crew.name))


@router.message(Command("foremen"))
async def cmd_list_foremen(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        foremen = await list_foremen(session)
    if not foremen:
        await message.answer(t("foremen_empty"))
        return
    lines = [f"• {f.name} (tg_id={f.tg_id})" for f in foremen]
    await message.answer(t("foremen_list", body="\n".join(lines)))


# --- FOREMAN ---


@router.message(Command("invite"))
@router.message(F.text == "\U0001f4e9 Пригласить")
async def cmd_invite(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        invite = await issue_invite_code(session, crew.id, db_user.id)
        await session.commit()
        code = invite.code
    await message.answer(t("invite_issued", code=code))


@router.message(Command("crew"))
async def cmd_crew(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    crew_name: str | None = None
    members: list[User] = []
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        crew_name = crew.name
        members = await list_crew_members(session, crew.id)
    assert crew_name is not None
    if not members:
        await message.answer(t("crew_empty", crew=crew_name))
        return
    lines = [f"• {m.name}" for m in members]
    await message.answer(t("crew_list", crew=crew_name, body="\n".join(lines)))


# --- FOREMAN REPORTS ---


async def _crew_period_summary(
    message: Message,
    db_user: User | None,
    start_date: date,
    end_date: date,
    empty_key: str,
    summary_key: str,
) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    rows: list[tuple[str, Decimal, int]] = []
    total_hours = Decimal(0)
    total_count = 0
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        members = await list_crew_members(session, crew.id)
        if not members:
            await message.answer(t(empty_key))
            return
        member_ids = [m.id for m in members]
        shifts = await get_shifts_for_users_in_period(
            session, member_ids, start_date, end_date, tz,
        )
        by_user: dict[int, list[Shift]] = {m.id: [] for m in members}
        for shift in shifts:
            if shift.end_at is not None:
                by_user[shift.user_id].append(shift)
        for member in members:
            user_shifts = by_user[member.id]
            hours = compute_period_hours(user_shifts, start_date, end_date, tz)
            count = len(user_shifts)
            if count == 0 and hours == 0:
                continue
            rows.append((member.name, hours, count))
            total_hours += hours
            total_count += count
    if not rows:
        await message.answer(t(empty_key))
        return
    body_lines = [f"• {name}: {hrs} ч ({n})" for name, hrs, n in rows]
    await message.answer(
        t(
            summary_key,
            body="\n".join(body_lines),
            total_hours=str(total_hours.quantize(Decimal('0.01'))),
            total_count=str(total_count),
        ),
    )


@router.message(Command("crew_today"))
@router.message(F.text.contains("Бригада сегодня"))
async def cmd_crew_today(message: Message, db_user: User | None = None) -> None:
    today = date.today()
    await _crew_period_summary(
        message, db_user, today, today, "crew_no_shifts_today", "crew_today_summary",
    )


@router.message(Command("crew_week"))
async def cmd_crew_week(message: Message, db_user: User | None = None) -> None:
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    await _crew_period_summary(
        message, db_user, start_of_week, today,
        "crew_no_shifts_week", "crew_week_summary",
    )


@router.message(Command("crew_month"))
async def cmd_crew_month(message: Message, db_user: User | None = None) -> None:
    today = date.today()
    start_of_month = today.replace(day=1)
    await _crew_period_summary(
        message, db_user, start_of_month, today,
        "crew_no_shifts_month", "crew_month_summary",
    )


_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


@router.message(Command("crew_export"))
async def cmd_crew_export(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    if not command.args or not _PERIOD_RE.match(command.args.strip()):
        await message.answer(t("crew_export_usage"))
        return
    period = command.args.strip()
    match = _PERIOD_RE.match(period)
    assert match is not None
    year, month = int(match.group(1)), int(match.group(2))
    start_date = date(year, month, 1)
    next_month = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    end_date = next_month - timedelta(days=1)

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        members = await list_crew_members(session, crew.id)
        if not members:
            await message.answer(t("crew_empty", crew=crew.name))
            return
        member_ids = [m.id for m in members]
        shifts = await get_shifts_for_users_in_period(
            session, member_ids, start_date, end_date, tz,
        )
        if not any(s.end_at is not None for s in shifts):
            await message.answer(t("export_empty", period=period))
            return
        shifts_by_user: dict[int, list[Shift]] = {m.id: [] for m in members}
        for shift in shifts:
            shifts_by_user[shift.user_id].append(shift)

        from sqlalchemy import select

        site_ids = {s.site_id for s in shifts if s.site_id}
        if site_ids:
            res = await session.execute(select(Site).where(Site.id.in_(site_ids)))
            sites_dict = {s.id: s for s in res.scalars().all()}
        else:
            sites_dict = {}

        buffer = export_crew_xlsx(
            crew, members, shifts_by_user, sites_dict, tz, period,
        )
        crew_name = crew.name

    safe_crew = re.sub(r"[^\w-]+", "_", crew_name)
    filename = f"crew_{safe_crew}_{period}.xlsx"
    doc = BufferedInputFile(buffer.read(), filename=filename)
    await message.answer_document(doc, caption=t("export_ready", period=period))


# --- WORKER ---


@router.message(Command("join"))
async def cmd_join(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("join_usage"))
        return
    code = command.args.strip().upper()
    async for session in get_session():
        # Reload user inside this session so changes persist correctly.
        from sqlalchemy import select

        from src.core.models import User as UserModel

        fresh = (
            await session.execute(
                select(UserModel).where(UserModel.id == db_user.id),
            )
        ).scalar_one()
        try:
            crew = await redeem_invite_code(session, code, fresh)
        except InviteError as exc:
            await message.answer(t("invite_error", reason=str(exc)))
            return
        await session.commit()
    await message.answer(t("joined_crew", crew=crew.name))
