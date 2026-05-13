"""Phase 5.2: /advance, /my_advances, /crew_advances, /salary, /crew_salary."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape as _esc
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from src.bot.handlers.accounting import cmd_period
from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.advances import (
    compute_salary,
    list_advances_for_period,
    list_advances_for_users_period,
    parse_amount,
    parse_year_month,
    record_advance,
)
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    get_crew_for_foreman,
    list_crew_members,
)
from src.services.day_entries import format_hours

router = Router()


def _is_admin(user: User | None) -> bool:
    return user is not None and user.role in (ROLE_OWNER, ROLE_FOREMAN)


def _current_year_month(tz: ZoneInfo) -> tuple[int, int]:
    now = datetime.now(tz=tz)
    return now.year, now.month


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


# --- /advance ---------------------------------------------------------------


@router.message(Command("advance"))
async def cmd_advance(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/advance <tg_id> <amount> [note]`` — foreman/owner records an advance."""
    if not _is_admin(db_user):
        await message.answer(t("not_authorized"))
        return
    assert db_user is not None
    if not command.args:
        await message.answer(t("advance_usage"))
        return
    parts = command.args.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(t("advance_usage"))
        return
    try:
        target_tg_id = int(parts[0])
    except ValueError:
        await message.answer(t("advance_usage"))
        return
    amount = parse_amount(parts[1])
    if amount is None:
        await message.answer(t("advance_bad_amount"))
        return
    note = parts[2].strip() if len(parts) == 3 else None

    target_name: str | None = None
    advance_day_iso: str | None = None
    async for session in get_session():
        target = (
            await session.execute(
                select(User).where(User.tg_id == target_tg_id),
            )
        ).scalar_one_or_none()
        if target is None:
            await message.answer(t("user_not_found"))
            return
        if db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None or target.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        settings = get_settings()
        tz = ZoneInfo(settings.timezone)
        today = datetime.now(tz=tz).date()
        adv = await record_advance(
            session,
            user_id=target.id,
            amount=amount,
            recorded_by_id=db_user.id,
            day=today,
            note=note,
        )
        await session.commit()
        target_name = target.name
        advance_day_iso = adv.day.isoformat()
    if target_name is None or advance_day_iso is None:
        return
    await message.answer(
        t(
            "advance_recorded",
            name=_esc(target_name),
            amount=_fmt_money(amount),
            date=advance_day_iso,
            note=_esc(note) if note else "—",
            currency=db_user.currency,
        ),
        parse_mode="HTML",
    )


# --- /my_advances -----------------------------------------------------------


@router.message(Command("my_advances"))
async def cmd_my_advances(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/my_advances`` (current month) or ``/my_advances YYYY-MM``."""
    if db_user is None:
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    if command.args:
        ym = parse_year_month(command.args)
        if ym is None:
            await message.answer(t("month_format"))
            return
        year, month = ym
    else:
        year, month = _current_year_month(tz)
    async for session in get_session():
        rows = await list_advances_for_period(
            session, user_id=db_user.id, year=year, month=month,
        )
    if not rows:
        await message.answer(t("advances_empty"), parse_mode="HTML")
        return
    cur = db_user.currency
    lines = [t("advances_header", year=year, month=f"{month:02d}")]
    total = Decimal(0)
    for a in rows:
        total += a.amount
        lines.append(
            t(
                "advance_row",
                date=a.day.isoformat(),
                amount=_fmt_money(a.amount),
                note=_esc(a.note) if a.note else "—",
                currency=cur,
            ),
        )
    lines.append(t("advances_total", total=_fmt_money(total), currency=cur))
    await message.answer("\n".join(lines), parse_mode="HTML")


# --- /crew_advances ---------------------------------------------------------


@router.message(Command("crew_advances"))
async def cmd_crew_advances(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/crew_advances [YYYY-MM]`` — foreman: all advances in the crew."""
    if not _is_admin(db_user):
        await message.answer(t("not_authorized"))
        return
    assert db_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    if command.args:
        ym = parse_year_month(command.args)
        if ym is None:
            await message.answer(t("month_format"))
            return
        year, month = ym
    else:
        year, month = _current_year_month(tz)

    async for session in get_session():
        if db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None:
                await message.answer(t("no_crew"))
                return
            members = await list_crew_members(session, crew.id)
        else:
            members = list(
                (await session.execute(select(User))).scalars().all(),
            )
        member_ids = [m.id for m in members]
        grouped = await list_advances_for_users_period(
            session, user_ids=member_ids, year=year, month=month,
        )

    names = {m.id: m.name for m in members}
    any_rows = False
    lines = [t("crew_advances_header", year=year, month=f"{month:02d}")]
    crew_total = Decimal(0)
    for uid, advs in grouped.items():
        if not advs:
            continue
        any_rows = True
        sub_total = sum((a.amount for a in advs), Decimal(0))
        crew_total += sub_total
        lines.append(
            t(
                "crew_advances_member",
                name=_esc(names.get(uid, f"id={uid}")),
                total=_fmt_money(sub_total),
                n=len(advs),
                currency=db_user.currency,
            ),
        )
    if not any_rows:
        await message.answer(t("advances_empty"), parse_mode="HTML")
        return
    lines.append(
        t("advances_total", total=_fmt_money(crew_total), currency=db_user.currency),
    )
    await message.answer("\n".join(lines), parse_mode="HTML")


# --- /salary ----------------------------------------------------------------


@router.message(Command("salary"))
async def cmd_salary(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/salary`` is an alias for ``/period`` — same period-aware view.

    Kept so existing button/menu shortcuts continue to work; the new
    payment-aware report lives in ``handlers.accounting``.
    """
    await cmd_period(message, command, db_user=db_user)


# --- /crew_salary -----------------------------------------------------------


@router.message(Command("crew_salary"))
async def cmd_crew_salary(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/crew_salary [YYYY-MM]`` — foreman/owner: salary summary per member."""
    if not _is_admin(db_user):
        await message.answer(t("not_authorized"))
        return
    assert db_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    if command.args:
        ym = parse_year_month(command.args)
        if ym is None:
            await message.answer(t("month_format"))
            return
        year, month = ym
    else:
        year, month = _current_year_month(tz)

    async for session in get_session():
        if db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None:
                await message.answer(t("no_crew"))
                return
            members = await list_crew_members(session, crew.id)
        else:
            members = list(
                (await session.execute(select(User))).scalars().all(),
            )
        breakdowns = []
        for m in members:
            b = await compute_salary(session, user=m, year=year, month=month, tz=tz)
            breakdowns.append((m, b))

    rows_with_data = [
        (m, b) for m, b in breakdowns
        if b.total_hours > 0 or b.advances_total > 0
    ]
    if not rows_with_data:
        await message.answer(t("crew_salary_empty"), parse_mode="HTML")
        return

    lines = [t("crew_salary_header", year=year, month=f"{month:02d}")]
    grand_total = Decimal(0)
    grand_priced = False
    for m, b in rows_with_data:
        if b.net_payable is not None:
            grand_total += b.net_payable
            grand_priced = True
        lines.append(
            t(
                "crew_salary_row",
                name=_esc(m.name),
                hours=format_hours(b.total_hours),
                advances=_fmt_money(b.advances_total),
                net=_fmt_money(b.net_payable),
                currency=m.currency,
            ),
        )
    lines.append(
        t(
            "crew_salary_total",
            total=_fmt_money(grand_total) if grand_priced else "—",
            currency=db_user.currency,
        ),
    )
    await message.answer("\n".join(lines), parse_mode="HTML")
