"""Phase 6.3: first-run onboarding wizard.

Flow: triggered by `cmd_start` (in `common.py`) when a brand-new user's
``onboarded_at`` is NULL. Walks them through three steps via FSM:

1. Name (default = Telegram full_name; inline button to accept, or text)
2. Hourly rate in PLN (or skip)
3. Evening reminder hour (19:00 / 20:00 / no)

On completion we set ``users.onboarded_at`` and show the simple-mode
reply keyboard. ``/cancel`` aborts; the next ``/start`` re-runs the
wizard since the column stayed NULL.
"""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from src.bot.keyboards import simple_menu
from src.bot.states import Onboarding
from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.app_settings import get_settings as get_app_settings
from src.services.onboarding import complete_onboarding, parse_rate

router = Router()

# Callback-data namespaces. Telegram limits callback_data to 64 bytes.
_CB_NAME_USE_TG = "onb:name:tg"
_CB_CURRENCY = "onb:cur:"  # onb:cur:PLN, onb:cur:USD, ...
_CB_RATE_SKIP = "onb:rate:skip"
_CB_REMIND = "onb:rmd:"  # onb:rmd:19, onb:rmd:20, onb:rmd:no

_CURRENCY_PRESETS: tuple[str, ...] = ("PLN", "USD", "EUR", "RUB", "BYN", "UAH")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


def _name_keyboard(tg_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("onb_name_use_tg_btn", tg_name=tg_name),
                    callback_data=_CB_NAME_USE_TG,
                ),
            ],
        ],
    )


def _currency_keyboard() -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(text=cur, callback_data=f"{_CB_CURRENCY}{cur}")
        for cur in _CURRENCY_PRESETS
    ]
    rows = [btns[i : i + 3] for i in range(0, len(btns), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _rate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("onb_rate_skip_btn"), callback_data=_CB_RATE_SKIP,
                ),
            ],
        ],
    )


def _reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("onb_reminder_btn_19"),
                    callback_data=f"{_CB_REMIND}19",
                ),
                InlineKeyboardButton(
                    text=t("onb_reminder_btn_20"),
                    callback_data=f"{_CB_REMIND}20",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("onb_reminder_btn_no"),
                    callback_data=f"{_CB_REMIND}no",
                ),
            ],
        ],
    )


async def start_wizard(
    message: Message, state: FSMContext, db_user: User,
) -> None:
    """Entry point: send the welcome + name prompt and enter the FSM."""
    tg_name = (
        message.from_user.full_name
        if message.from_user is not None
        else db_user.name
    )
    await state.clear()
    await state.set_state(Onboarding.awaiting_name)
    await state.update_data(tg_name=tg_name)
    await message.answer(
        t("onb_welcome", name=tg_name),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        t("onb_name_prompt", tg_name=tg_name),
        reply_markup=_name_keyboard(tg_name),
    )


@router.callback_query(Onboarding.awaiting_name, F.data == _CB_NAME_USE_TG)
async def cb_name_use_tg(
    query: CallbackQuery, state: FSMContext, db_user: User | None = None,
) -> None:
    data = await state.get_data()
    tg_name = str(data.get("tg_name") or "")
    currency = db_user.currency if db_user else "PLN"
    await _accept_name(query, state, tg_name, currency=currency)
    await query.answer()


@router.message(Onboarding.awaiting_name, F.text)
async def msg_name(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer(t("onb_name_bad"))
        return
    currency = db_user.currency if db_user else "PLN"
    await _accept_name(message, state, raw, currency=currency)


async def _accept_name(
    source: Message | CallbackQuery,
    state: FSMContext,
    name: str,
    currency: str = "PLN",
) -> None:
    await state.update_data(name=name, currency=currency)
    await state.set_state(Onboarding.awaiting_currency)
    target = source.message if isinstance(source, CallbackQuery) else source
    if target is None:
        return
    await target.answer(t("onb_name_saved", name=name))
    await target.answer(
        t("onb_currency_prompt"), reply_markup=_currency_keyboard(),
    )


async def _accept_currency(
    source: Message | CallbackQuery,
    state: FSMContext,
    currency: str,
) -> None:
    await state.update_data(currency=currency)
    await state.set_state(Onboarding.awaiting_rate)
    target = source.message if isinstance(source, CallbackQuery) else source
    if target is None:
        return
    await target.answer(t("onb_currency_saved", currency=currency))
    await target.answer(
        t("onb_rate_prompt", currency=currency), reply_markup=_rate_keyboard(),
    )


@router.callback_query(Onboarding.awaiting_currency, F.data.startswith(_CB_CURRENCY))
async def cb_currency_pick(
    query: CallbackQuery, state: FSMContext,
) -> None:
    if query.data is None:
        await query.answer()
        return
    currency = query.data[len(_CB_CURRENCY):].upper()
    if not _CURRENCY_RE.fullmatch(currency):
        await query.answer()
        return
    await _accept_currency(query, state, currency)
    await query.answer()


@router.message(Onboarding.awaiting_currency, F.text)
async def msg_currency(
    message: Message, state: FSMContext,
) -> None:
    raw = (message.text or "").strip().upper()
    if not _CURRENCY_RE.fullmatch(raw):
        await message.answer(t("onb_currency_bad"))
        return
    await _accept_currency(message, state, raw)


@router.callback_query(Onboarding.awaiting_rate, F.data == _CB_RATE_SKIP)
async def cb_rate_skip(query: CallbackQuery, state: FSMContext) -> None:
    target = query.message
    if isinstance(target, Message):
        await target.answer(t("onb_rate_skipped"))
    await state.update_data(rate=None)
    await state.set_state(Onboarding.awaiting_reminder)
    if isinstance(target, Message):
        await target.answer(
            t("onb_reminder_prompt"), reply_markup=_reminder_keyboard(),
        )
    await query.answer()


@router.message(Onboarding.awaiting_rate, F.text)
async def msg_rate(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    rate = parse_rate(message.text or "")
    if rate is None:
        await message.answer(t("onb_rate_bad"))
        return
    await state.update_data(rate=str(rate))
    data = await state.get_data()
    currency = str(data.get("currency") or (db_user.currency if db_user else "PLN"))
    await message.answer(t("onb_rate_saved", rate=str(rate), currency=currency))
    await state.set_state(Onboarding.awaiting_reminder)
    await message.answer(
        t("onb_reminder_prompt"), reply_markup=_reminder_keyboard(),
    )


@router.callback_query(Onboarding.awaiting_reminder, F.data.startswith(_CB_REMIND))
async def cb_reminder(
    query: CallbackQuery, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    choice = query.data[len(_CB_REMIND):]
    hour: int | None
    if choice == "no":
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
    await _finish(query, state, db_user=db_user, hour=hour)
    await query.answer()


async def _finish(
    source: Message | CallbackQuery,
    state: FSMContext,
    *,
    db_user: User,
    hour: int | None,
) -> None:
    from decimal import Decimal

    data = await state.get_data()
    name = str(data.get("name") or db_user.name)
    rate_raw = data.get("rate")
    rate = Decimal(str(rate_raw)) if rate_raw is not None else None
    currency_raw = data.get("currency")
    currency = str(currency_raw) if currency_raw else None

    target = source.message if isinstance(source, CallbackQuery) else source
    if target is None:
        return

    async for session in get_session():
        await complete_onboarding(
            session,
            user_id=db_user.id,
            name=name,
            hourly_rate=rate,
            remind_hour_local=hour,
            currency=currency,
        )
        snap = await get_app_settings(session)
        await session.commit()

    await state.clear()
    if hour is None:
        await target.answer(t("onb_reminder_skipped"))
    else:
        await target.answer(t("onb_reminder_saved", hour=f"{hour:02d}"))
    await target.answer(
        t("onb_done"), reply_markup=simple_menu(snap, db_user.role),
    )


@router.message(Onboarding(), Command("cancel"))
async def msg_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("onb_cancelled"), reply_markup=ReplyKeyboardRemove())
