"""Phase 6.6: inline calendar — pick a date, edit data for that day.

Lets a worker open a month grid in Telegram, tap any date, and:
  - set the day's hours (quick-pick) or mark it a day off
  - record an advance (PLN) taken on that date
  - record a salary payment, with separate accounting period
    (e.g. paid on 2026-05-05 *for* 2026-04 work)

Callback grammar (all comfortably under Telegram's 64-byte limit):
  cal:nav:YYYY-MM            -> show month grid
  cal:day:YYYY-MM-DD         -> open day detail
  cal:hrs:YYYY-MM-DD         -> open hours picker for day
  cal:set:YYYY-MM-DD:H       -> set H hours for day (0 = day off)
  cal:adv:YYYY-MM-DD         -> start advance amount entry (FSM)
  cal:pay:YYYY-MM-DD         -> show period picker for salary payment
  cal:per:YYYY-MM-DD:YYYY-MM -> select period -> start payment amount entry
  cal:noop                   -> placeholder (month header / blank cell)
"""

from __future__ import annotations

import calendar as cal_mod
import contextlib
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

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

from src.bot.states import CalendarFlow
from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Advance, DayEntry, SalaryPayment, User
from src.services.advances import list_advances, parse_amount, record_advance
from src.services.day_entries import (
    QUICK_HOURS,
    format_hours,
    get_day_entry,
    is_day_off,
    parse_hours,
    upsert_day_entry,
)
from src.services.salary_payments import (
    list_payments_paid_on,
    record_payment,
)

router = Router()

# --- Callback-data namespaces (kept short — Telegram limits to 64 bytes) ---
_NS = "cal:"
_NAV = _NS + "nav:"
_DAY = _NS + "day:"
_HRS = _NS + "hrs:"
_SET = _NS + "set:"
_ADV = _NS + "adv:"
_PAY = _NS + "pay:"
_PER = _NS + "per:"
_NOOP = _NS + "noop"

_RU_MONTHS: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)
_RU_DOW: tuple[str, ...] = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def _today_local() -> date:
    tz = ZoneInfo(get_settings().timezone)
    return datetime.now(tz=tz).date()


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _month_header_text(year: int, month: int) -> str:
    return t("cal_header", month=_RU_MONTHS[month - 1], year=year)


async def _build_month_keyboard(
    session: AsyncSession, *, user_id: int, year: int, month: int,
) -> InlineKeyboardMarkup:
    """Render the inline keyboard for one month, with markers on days with data."""
    today = _today_local()
    last_day_num = cal_mod.monthrange(year, month)[1]
    first = date(year, month, 1)
    last = date(year, month, last_day_num)

    de_rows = list(
        (
            await session.execute(
                select(DayEntry).where(
                    DayEntry.user_id == user_id,
                    DayEntry.day >= first,
                    DayEntry.day <= last,
                ),
            )
        ).scalars().all(),
    )
    adv_rows = list(
        (
            await session.execute(
                select(Advance.day).where(
                    Advance.user_id == user_id,
                    Advance.day >= first,
                    Advance.day <= last,
                ),
            )
        ).scalars().all(),
    )
    pay_rows = list(
        (
            await session.execute(
                select(SalaryPayment.paid_on).where(
                    SalaryPayment.user_id == user_id,
                    SalaryPayment.paid_on >= first,
                    SalaryPayment.paid_on <= last,
                ),
            )
        ).scalars().all(),
    )

    de_by_day: dict[date, DayEntry] = {e.day: e for e in de_rows}
    adv_set: set[date] = set(adv_rows)
    pay_set: set[date] = set(pay_rows)

    py, pm = _prev_month(year, month)
    ny, nm = _next_month(year, month)

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="◀", callback_data=f"{_NAV}{py}-{pm:02d}"),
            InlineKeyboardButton(
                text=f"{_RU_MONTHS[month - 1]} {year}", callback_data=_NOOP,
            ),
            InlineKeyboardButton(text="▶", callback_data=f"{_NAV}{ny}-{nm:02d}"),
        ],
        [InlineKeyboardButton(text=lbl, callback_data=_NOOP) for lbl in _RU_DOW],
    ]

    grid: list[InlineKeyboardButton] = []
    # Leading blanks so column 0 is Monday.
    for _ in range(first.weekday()):
        grid.append(InlineKeyboardButton(text=" ", callback_data=_NOOP))
    for d in range(1, last_day_num + 1):
        the_day = date(year, month, d)
        marker = ""
        if the_day in de_by_day:
            entry = de_by_day[the_day]
            marker = "🌴" if is_day_off(entry.hours) else "•"
        elif the_day in pay_set:
            marker = "💰"
        elif the_day in adv_set:
            marker = "💵"
        label = f"{d}{marker}" if marker else str(d)
        if the_day == today:
            label = f"·{label}·"
        grid.append(
            InlineKeyboardButton(
                text=label, callback_data=f"{_DAY}{the_day.isoformat()}",
            ),
        )
    # Trailing blanks to fill the final week.
    while len(grid) % 7:
        grid.append(InlineKeyboardButton(text=" ", callback_data=_NOOP))
    for i in range(0, len(grid), 7):
        rows.append(grid[i : i + 7])

    rows.append(
        [InlineKeyboardButton(text=t("cal_legend"), callback_data=_NOOP)],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _build_day_view(
    session: AsyncSession, *, user_id: int, day: date, currency: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """Compose the per-day text + actions inline keyboard."""
    entry = await get_day_entry(session, user_id=user_id, day=day)
    advs = await list_advances(session, user_id=user_id, start=day, end=day)
    pays = await list_payments_paid_on(session, user_id=user_id, day=day)

    lines: list[str] = [t("cal_day_header", date=day.isoformat())]
    if entry is None:
        lines.append(t("cal_day_no_entry"))
    elif is_day_off(entry.hours):
        lines.append(t("cal_day_off_line"))
    else:
        lines.append(t("cal_day_hours", hours=format_hours(entry.hours)))
    if advs:
        total_a = sum((a.amount for a in advs), Decimal(0))
        lines.append(
            t(
                "cal_day_advances",
                n=len(advs),
                total=f"{total_a:.2f}",
                currency=currency,
            ),
        )
    if pays:
        total_p = sum((p.amount for p in pays), Decimal(0))
        lines.append(
            t(
                "cal_day_payments",
                n=len(pays),
                total=f"{total_p:.2f}",
                currency=currency,
            ),
        )
        for p in pays:
            lines.append(
                t(
                    "cal_day_payment_row",
                    amount=f"{p.amount:.2f}",
                    period=f"{p.period_year}-{p.period_month:02d}",
                    currency=currency,
                ),
            )

    iso = day.isoformat()
    kb_rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t("cal_btn_set_hours"), callback_data=f"{_HRS}{iso}")],
        [
            InlineKeyboardButton(
                text=t("cal_btn_dayoff"), callback_data=f"{_SET}{iso}:0",
            ),
        ],
        [InlineKeyboardButton(text=t("cal_btn_advance"), callback_data=f"{_ADV}{iso}")],
        [InlineKeyboardButton(text=t("cal_btn_payment"), callback_data=f"{_PAY}{iso}")],
        [
            InlineKeyboardButton(
                text=t("cal_btn_back"),
                callback_data=f"{_NAV}{day.year}-{day.month:02d}",
            ),
        ],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)


def _hours_picker_keyboard(day: date) -> InlineKeyboardMarkup:
    iso = day.isoformat()
    btns = [
        InlineKeyboardButton(
            text=f"{format_hours(v)} ч",
            callback_data=f"{_SET}{iso}:{format_hours(v)}",
        )
        for v in QUICK_HOURS
    ]
    rows = [btns[i : i + 3] for i in range(0, len(btns), 3)]
    rows.append(
        [
            InlineKeyboardButton(
                text=t("cal_btn_back_to_day"), callback_data=f"{_DAY}{iso}",
            ),
        ],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _period_keyboard(paid_on: date) -> InlineKeyboardMarkup:
    """Three quick period options (prev, current, prev-prev) + cancel.

    Defaults are anchored to the payment date because in practice salary is
    paid right after the period ends — "prev month" is the dominant case.
    """
    py_curr, pm_curr = paid_on.year, paid_on.month
    py_prev, pm_prev = _prev_month(py_curr, pm_curr)
    py_prev2, pm_prev2 = _prev_month(py_prev, pm_prev)
    iso = paid_on.isoformat()

    def row(year: int, month: int) -> list[InlineKeyboardButton]:
        return [
            InlineKeyboardButton(
                text=t("cal_per_btn", month=_RU_MONTHS[month - 1], year=year),
                callback_data=f"{_PER}{iso}:{year}-{month:02d}",
            ),
        ]

    rows = [
        row(py_prev, pm_prev),
        row(py_curr, pm_curr),
        row(py_prev2, pm_prev2),
        [
            InlineKeyboardButton(
                text=t("cal_btn_back_to_day"), callback_data=f"{_DAY}{iso}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Entry point ----------------------------------------------------------


@router.message(Command("calendar"))
async def cmd_calendar(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    await state.clear()
    today = _today_local()
    async for session in get_session():
        kb = await _build_month_keyboard(
            session, user_id=db_user.id, year=today.year, month=today.month,
        )
    await message.answer(_month_header_text(today.year, today.month), reply_markup=kb)


# --- Callbacks ------------------------------------------------------------


@router.callback_query(F.data == _NOOP)
async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()


@router.callback_query(F.data.startswith(_NAV))
async def cb_nav(query: CallbackQuery, db_user: User | None = None) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    raw = query.data[len(_NAV) :]
    try:
        year_s, month_s = raw.split("-")
        year, month = int(year_s), int(month_s)
    except ValueError:
        await query.answer()
        return
    if not (1 <= month <= 12):
        await query.answer()
        return
    async for session in get_session():
        kb = await _build_month_keyboard(
            session, user_id=db_user.id, year=year, month=month,
        )
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(
                _month_header_text(year, month), reply_markup=kb,
            )
    await query.answer()


@router.callback_query(F.data.startswith(_DAY))
async def cb_day(query: CallbackQuery, db_user: User | None = None) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    try:
        day = date.fromisoformat(query.data[len(_DAY) :])
    except ValueError:
        await query.answer()
        return
    async for session in get_session():
        body, kb = await _build_day_view(
            session, user_id=db_user.id, day=day, currency=db_user.currency,
        )
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(body, reply_markup=kb)
    await query.answer()


@router.callback_query(F.data.startswith(_HRS))
async def cb_hours_picker(
    query: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    try:
        day = date.fromisoformat(query.data[len(_HRS) :])
    except ValueError:
        await query.answer()
        return
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(
                t("cal_pick_hours", date=day.isoformat()),
                reply_markup=_hours_picker_keyboard(day),
            )
    await query.answer()


@router.callback_query(F.data.startswith(_SET))
async def cb_set_hours(
    query: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    raw = query.data[len(_SET) :]
    try:
        iso, hours_raw = raw.split(":")
        day = date.fromisoformat(iso)
    except ValueError:
        await query.answer()
        return
    hours = parse_hours(hours_raw)
    if hours is None:
        await query.answer(t("h_bad_value"), show_alert=True)
        return
    async for session in get_session():
        await upsert_day_entry(
            session, user_id=db_user.id, day=day, hours=hours,
        )
        await session.commit()
        body, kb = await _build_day_view(
            session, user_id=db_user.id, day=day, currency=db_user.currency,
        )
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(body, reply_markup=kb)
    await query.answer(t("settings_saved"))


# --- Advance flow ---------------------------------------------------------


@router.callback_query(F.data.startswith(_ADV))
async def cb_advance_start(
    query: CallbackQuery,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    try:
        day = date.fromisoformat(query.data[len(_ADV) :])
    except ValueError:
        await query.answer()
        return
    await state.set_state(CalendarFlow.awaiting_advance_amount)
    await state.update_data(day=day.isoformat())
    if isinstance(query.message, Message):
        await query.message.answer(
            t(
                "cal_advance_prompt",
                date=day.isoformat(),
                currency=db_user.currency,
            ),
        )
    await query.answer()


@router.message(CalendarFlow.awaiting_advance_amount, F.text)
async def msg_advance_amount(
    message: Message,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer(t("advance_bad_amount"))
        return
    data = await state.get_data()
    try:
        day = date.fromisoformat(str(data.get("day") or ""))
    except ValueError:
        await state.clear()
        return
    async for session in get_session():
        await record_advance(
            session,
            user_id=db_user.id,
            amount=amount,
            recorded_by_id=db_user.id,
            day=day,
            note=None,
        )
        await session.commit()
        body, kb = await _build_day_view(
            session, user_id=db_user.id, day=day, currency=db_user.currency,
        )
    await state.clear()
    await message.answer(
        t(
            "cal_advance_recorded",
            amount=f"{amount:.2f}",
            date=day.isoformat(),
            currency=db_user.currency,
        ),
    )
    await message.answer(body, reply_markup=kb)


# --- Salary payment flow --------------------------------------------------


@router.callback_query(F.data.startswith(_PAY))
async def cb_pay_start(
    query: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    try:
        day = date.fromisoformat(query.data[len(_PAY) :])
    except ValueError:
        await query.answer()
        return
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_text(
                t("cal_pay_pick_period", date=day.isoformat()),
                reply_markup=_period_keyboard(day),
            )
    await query.answer()


@router.callback_query(F.data.startswith(_PER))
async def cb_pay_period(
    query: CallbackQuery,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    raw = query.data[len(_PER) :]
    try:
        iso, period = raw.split(":")
        day = date.fromisoformat(iso)
        year_s, month_s = period.split("-")
        year, month = int(year_s), int(month_s)
    except ValueError:
        await query.answer()
        return
    if not (1 <= month <= 12) or not (2000 <= year <= 2100):
        await query.answer()
        return
    await state.set_state(CalendarFlow.awaiting_payment_amount)
    await state.update_data(
        day=day.isoformat(), period_year=year, period_month=month,
    )
    if isinstance(query.message, Message):
        await query.message.answer(
            t(
                "cal_pay_amount_prompt",
                date=day.isoformat(),
                period=f"{year}-{month:02d}",
                currency=db_user.currency,
            ),
        )
    await query.answer()


@router.message(CalendarFlow.awaiting_payment_amount, F.text)
async def msg_pay_amount(
    message: Message,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer(t("advance_bad_amount"))
        return
    data = await state.get_data()
    try:
        day = date.fromisoformat(str(data.get("day") or ""))
        year = int(data["period_year"])
        month = int(data["period_month"])
    except (KeyError, TypeError, ValueError):
        await state.clear()
        return
    async for session in get_session():
        await record_payment(
            session,
            user_id=db_user.id,
            paid_on=day,
            period_year=year,
            period_month=month,
            amount=amount,
            recorded_by_id=db_user.id,
        )
        await session.commit()
        body, kb = await _build_day_view(
            session, user_id=db_user.id, day=day, currency=db_user.currency,
        )
    await state.clear()
    await message.answer(
        t(
            "cal_pay_recorded",
            amount=f"{amount:.2f}",
            date=day.isoformat(),
            period=f"{year}-{month:02d}",
            currency=db_user.currency,
        ),
    )
    await message.answer(body, reply_markup=kb)


@router.message(CalendarFlow(), Command("cancel"))
async def msg_calendar_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("cancelled"))
