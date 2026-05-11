"""Phase 5.1: simple daily hours entry — `/h`, `/my_days`, `/edit_day`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.day_entries import (
    format_hours,
    get_day_entry,
    list_recent_entries,
    parse_hours,
    quick_pick_values,
    smart_suggest,
    upsert_day_entry,
)

router = Router()

# Callback data namespaces. Keep these short — Telegram limits callback_data to 64 bytes.
_CB_PICK_TODAY = "dh:"  # dh:<hours>  — set today's hours to <hours>
_CB_EDIT_DAY = "de:"  # de:<YYYY-MM-DD> — prompt to edit a specific day


def quick_keyboard(picks: list[Decimal]) -> InlineKeyboardMarkup:
    """Render the quick-pick row as an inline keyboard."""
    buttons: list[InlineKeyboardButton] = []
    for v in picks:
        label = f"{format_hours(v)} ч"
        buttons.append(
            InlineKeyboardButton(
                text=label, callback_data=f"{_CB_PICK_TODAY}{format_hours(v)}",
            ),
        )
    # 3 buttons per row.
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _today_for(_user: User | None) -> date:
    # Centralized so we can later swap to per-user timezone.
    return datetime.now().date()


async def _record(
    message_or_cq: Message | CallbackQuery,
    *,
    db_user: User,
    day: date,
    hours: Decimal,
) -> None:
    """Persist the entry and reply with a confirmation."""
    async for session in get_session():
        previous = await get_day_entry(session, user_id=db_user.id, day=day)
        previous_hours = previous.hours if previous is not None else None
        _, created = await upsert_day_entry(
            session, user_id=db_user.id, day=day, hours=hours,
        )
        await session.commit()
    text = (
        t("h_recorded_new", hours=format_hours(hours), date=day.isoformat())
        if created
        else t(
            "h_recorded_updated",
            old=format_hours(previous_hours) if previous_hours is not None else "—",
            hours=format_hours(hours),
            date=day.isoformat(),
        )
    )
    target = (
        message_or_cq.message
        if isinstance(message_or_cq, CallbackQuery)
        else message_or_cq
    )
    if target is not None:
        await target.answer(text)


@router.message(Command("h"))
async def cmd_h(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Set today's hours.

    With an arg: ``/h 8`` → records 8 hours for today.
    Without an arg: shows an inline keyboard with quick picks and (when
    habitual) a smart suggestion.
    """
    if db_user is None:
        return
    today = _today_for(db_user)
    if command.args:
        hours = parse_hours(command.args)
        if hours is None:
            await message.answer(t("h_bad_value"))
            return
        await _record(message, db_user=db_user, day=today, hours=hours)
        return

    async for session in get_session():
        recent = await list_recent_entries(session, user_id=db_user.id, days=14)
    suggested = smart_suggest(recent)
    picks = quick_pick_values(suggested)
    prompt = (
        t("h_prompt_with_suggest", suggest=format_hours(suggested))
        if suggested is not None
        else t("h_prompt")
    )
    await message.answer(prompt, reply_markup=quick_keyboard(picks))


@router.callback_query(F.data.startswith(_CB_PICK_TODAY))
async def cb_pick_today(query: CallbackQuery, db_user: User | None = None) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    raw = query.data[len(_CB_PICK_TODAY) :]
    hours = parse_hours(raw)
    if hours is None:
        await query.answer(t("h_bad_value"), show_alert=True)
        return
    await _record(query, db_user=db_user, day=_today_for(db_user), hours=hours)
    await query.answer()


@router.message(Command("edit_day"))
async def cmd_edit_day(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/edit_day YYYY-MM-DD <hours>`` — overwrite the entry for that day."""
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("h_edit_usage"))
        return
    parts = command.args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(t("h_edit_usage"))
        return
    try:
        day = date.fromisoformat(parts[0])
    except ValueError:
        await message.answer(t("h_bad_date"))
        return
    hours = parse_hours(parts[1])
    if hours is None:
        await message.answer(t("h_bad_value"))
        return
    await _record(message, db_user=db_user, day=day, hours=hours)


@router.message(Command("remind_on"))
async def cmd_remind_on(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/remind_on HH`` — set the local hour for the evening reminder."""
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("remind_on_usage"))
        return
    raw = command.args.strip()
    try:
        hour = int(raw)
    except ValueError:
        await message.answer(t("remind_bad_hour"))
        return
    if not (0 <= hour <= 23):
        await message.answer(t("remind_bad_hour"))
        return
    async for session in get_session():
        user = await session.get(User, db_user.id)
        if user is None:
            return
        user.remind_hour_local = hour
        # Reset idempotency so a same-day re-arm fires today if hour is reached.
        user.day_reminder_last_sent = None
        await session.commit()
    await message.answer(t("remind_on_ok", hour=f"{hour:02d}"))


@router.message(Command("remind_off"))
async def cmd_remind_off(
    message: Message, db_user: User | None = None,
) -> None:
    """``/remind_off`` — disable the evening reminder for this user."""
    if db_user is None:
        return
    async for session in get_session():
        user = await session.get(User, db_user.id)
        if user is None:
            return
        user.remind_hour_local = None
        await session.commit()
    await message.answer(t("remind_off_ok"))


@router.message(Command("my_days"))
async def cmd_my_days(message: Message, db_user: User | None = None) -> None:
    """Last 14 days of the user's day-entries with a total at the bottom."""
    if db_user is None:
        return
    async for session in get_session():
        entries = await list_recent_entries(session, user_id=db_user.id, days=14)
    if not entries:
        await message.answer(t("my_days_empty"))
        return
    lines = [t("my_days_header")]
    total = Decimal(0)
    for e in entries:
        lines.append(
            t(
                "my_days_row",
                date=e.day.isoformat(),
                hours=format_hours(e.hours),
            ),
        )
        total += e.hours
    lines.append(t("my_days_total", total=format_hours(total), n=len(entries)))
    await message.answer("\n".join(lines))
