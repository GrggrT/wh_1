"""Phase 6.9: /profile editor.

Single inline view with four edit buttons: name, hourly rate, currency,
evening reminder hour. Each button enters a one-step FSM that updates the
``users`` row and re-renders the profile.
"""

from __future__ import annotations

import contextlib
import re
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import ProfileEdit
from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.advances import parse_amount

router = Router()

_CB_NAME = "prof:name"
_CB_RATE = "prof:rate"
_CB_CUR = "prof:cur"
_CB_RMD = "prof:rmd"
_CB_RMD_SET = "prof:rmd:"  # prof:rmd:19, prof:rmd:off
_CB_CLOSE = "prof:close"

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_REMINDER_PRESETS: tuple[int, ...] = (18, 19, 20, 21)


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("profile_btn_name"), callback_data=_CB_NAME),
                InlineKeyboardButton(text=t("profile_btn_rate"), callback_data=_CB_RATE),
            ],
            [
                InlineKeyboardButton(text=t("profile_btn_currency"), callback_data=_CB_CUR),
                InlineKeyboardButton(text=t("profile_btn_reminder"), callback_data=_CB_RMD),
            ],
            [InlineKeyboardButton(text=t("profile_btn_close"), callback_data=_CB_CLOSE)],
        ],
    )


def _reminder_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    btns = [
        InlineKeyboardButton(
            text=f"{h:02d}:00", callback_data=f"{_CB_RMD_SET}{h}",
        )
        for h in _REMINDER_PRESETS
    ]
    rows.append(btns)
    rows.append(
        [
            InlineKeyboardButton(
                text=t("profile_reminder_btn_off"),
                callback_data=f"{_CB_RMD_SET}off",
            ),
        ],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_profile(user: User) -> str:
    rate = (
        f"{user.hourly_rate} {user.currency}/ч"
        if user.hourly_rate is not None
        else t("profile_rate_none")
    )
    if user.remind_hour_local is None:
        reminder = t("profile_reminder_none")
    else:
        reminder = t("profile_reminder_at", hour=f"{user.remind_hour_local:02d}")
    return t(
        "profile_header",
        name=user.name,
        rate=rate,
        currency=user.currency,
        reminder=reminder,
    )


async def _fetch_user(session: AsyncSession, tg_id: int) -> User | None:
    return (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()


@router.message(Command("profile"))
async def cmd_profile(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    await state.clear()
    await message.answer(_render_profile(db_user), reply_markup=_profile_keyboard())


@router.callback_query(F.data == _CB_CLOSE)
async def cb_close(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(t("profile_closed"))
    await query.answer()


# --- Name ----------------------------------------------------------------


@router.callback_query(F.data == _CB_NAME)
async def cb_name(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEdit.awaiting_name)
    if isinstance(query.message, Message):
        await query.message.answer(t("profile_name_prompt"))
    await query.answer()


@router.message(ProfileEdit.awaiting_name, F.text)
async def msg_name(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    raw = (message.text or "").strip()
    if not raw or raw.startswith("/"):
        await message.answer(t("profile_name_bad"))
        return
    name = raw[:80]
    async for session in get_session():
        user = await _fetch_user(session, db_user.tg_id)
        if user is None:
            return
        user.name = name
        await session.commit()
        await session.refresh(user)
        rendered = _render_profile(user)
    await state.clear()
    await message.answer(t("profile_name_saved", name=name))
    await message.answer(rendered, reply_markup=_profile_keyboard())


# --- Hourly rate ---------------------------------------------------------


@router.callback_query(F.data == _CB_RATE)
async def cb_rate(
    query: CallbackQuery, state: FSMContext, db_user: User | None = None,
) -> None:
    await state.set_state(ProfileEdit.awaiting_rate)
    if isinstance(query.message, Message) and db_user is not None:
        await query.message.answer(
            t("profile_rate_prompt", currency=db_user.currency),
        )
    await query.answer()


@router.message(ProfileEdit.awaiting_rate, F.text)
async def msg_rate(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    raw = (message.text or "").strip()
    cleared = raw in {"-", "—"}
    rate: Decimal | None
    if cleared:
        rate = None
    else:
        parsed = parse_amount(raw)
        if parsed is None:
            await message.answer(t("profile_rate_bad"))
            return
        rate = parsed
    async for session in get_session():
        user = await _fetch_user(session, db_user.tg_id)
        if user is None:
            return
        user.hourly_rate = rate
        await session.commit()
        await session.refresh(user)
        rendered = _render_profile(user)
        cur = user.currency
    await state.clear()
    if rate is None:
        await message.answer(t("profile_rate_cleared"))
    else:
        await message.answer(t("profile_rate_saved", rate=str(rate), currency=cur))
    await message.answer(rendered, reply_markup=_profile_keyboard())


# --- Currency ------------------------------------------------------------


@router.callback_query(F.data == _CB_CUR)
async def cb_currency(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEdit.awaiting_currency)
    if isinstance(query.message, Message):
        await query.message.answer(t("profile_currency_prompt"))
    await query.answer()


@router.message(ProfileEdit.awaiting_currency, F.text)
async def msg_currency(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    raw = (message.text or "").strip().upper()
    if not _CURRENCY_RE.fullmatch(raw):
        await message.answer(t("profile_currency_bad"))
        return
    async for session in get_session():
        user = await _fetch_user(session, db_user.tg_id)
        if user is None:
            return
        user.currency = raw
        await session.commit()
        await session.refresh(user)
        rendered = _render_profile(user)
    await state.clear()
    await message.answer(t("profile_currency_saved", currency=raw))
    await message.answer(rendered, reply_markup=_profile_keyboard())


# --- Reminder ------------------------------------------------------------


@router.callback_query(F.data == _CB_RMD)
async def cb_reminder(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEdit.awaiting_remind_hour)
    if isinstance(query.message, Message):
        await query.message.answer(
            t("profile_reminder_prompt"), reply_markup=_reminder_keyboard(),
        )
    await query.answer()


@router.callback_query(F.data.startswith(_CB_RMD_SET))
async def cb_reminder_set(
    query: CallbackQuery, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    choice = query.data[len(_CB_RMD_SET):]
    hour: int | None
    if choice == "off":
        hour = None
    else:
        try:
            hour = int(choice)
        except ValueError:
            await query.answer()
            return
        if not (0 <= hour <= 23):
            await query.answer()
            return
    async for session in get_session():
        user = await _fetch_user(session, db_user.tg_id)
        if user is None:
            await query.answer()
            return
        user.remind_hour_local = hour
        user.day_reminder_last_sent = None
        await session.commit()
        await session.refresh(user)
        rendered = _render_profile(user)
    await state.clear()
    value = t("profile_reminder_none") if hour is None else f"{hour:02d}:00"
    if isinstance(query.message, Message):
        await query.message.answer(t("profile_reminder_saved", value=value))
        await query.message.answer(rendered, reply_markup=_profile_keyboard())
    await query.answer()


@router.message(ProfileEdit(), Command("cancel"))
async def msg_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("cancelled"))
