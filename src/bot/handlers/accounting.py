"""Phase 6.7: ``/period``, ``/cash``, ``/owed`` — accounting-clear reports.

These commands answer three distinct questions that the old ``/salary`` view
conflated:

- ``/period`` — for *this work month*, how much did I earn, how much has
  been paid (advances + payments tagged with this period), how much is
  left? Late payments arriving in following months still show up here
  with a "← выплачено в <month>" tag, because the period field is what
  matters for accounting.
- ``/cash``   — what *physical* cash moved this month? Useful for matching
  bank/wallet statements. Each row carries the period it covers in
  parentheses, so an early-May payment for April is easy to spot.
- ``/owed``   — which past periods are still unpaid or partially paid?
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.accounting import (
    CashflowEntry,
    PeriodLedger,
    get_period_ledger,
    list_cashflow,
    list_open_periods,
)
from src.services.advances import month_bounds, parse_year_month
from src.services.day_entries import format_hours

router = Router()


_RU_MONTHS: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


def _ru_month(month: int) -> str:
    return _RU_MONTHS[month - 1]


def _fmt_money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _period_label(year: int, month: int) -> str:
    return f"{_ru_month(month)} {year}"


def _current_year_month(tz: ZoneInfo) -> tuple[int, int]:
    now = datetime.now(tz=tz)
    return now.year, now.month


def _rate_for_user(user: User) -> str:
    if user.hourly_rate is None:
        return "—"
    return f"{user.hourly_rate:.2f} {user.currency}/ч"


def format_period(ledger: PeriodLedger, user: User) -> str:
    """Format a PeriodLedger as a multi-line user-facing report."""
    cur = user.currency
    lines: list[str] = [
        t("period_header", month=_ru_month(ledger.month), year=ledger.year),
    ]
    if user.hourly_rate is None:
        lines.append(t("period_no_rate", hours=format_hours(ledger.hours)))
    else:
        lines.append(
            t(
                "period_hours_rate",
                hours=format_hours(ledger.hours),
                rate=_rate_for_user(user),
            ),
        )
    if ledger.earnings is None:
        lines.append(t("period_earnings_unpriced"))
    else:
        lines.append(
            t("period_earnings", earnings=_fmt_money(ledger.earnings), currency=cur),
        )

    # Advances list.
    if ledger.advances:
        lines.append("")
        lines.append(
            t(
                "period_advances_header",
                total=_fmt_money(ledger.advances_total),
                currency=cur,
            ),
        )
        for a in ledger.advances:
            lines.append(
                t(
                    "period_advance_row",
                    date=a.day.isoformat(),
                    amount=_fmt_money(a.amount),
                    note=a.note or "—",
                    currency=cur,
                ),
            )
    else:
        lines.append("")
        lines.append(t("period_no_advances"))

    # Payments list, tagging late payments with their physical paid_on month.
    if ledger.payments:
        lines.append("")
        lines.append(
            t(
                "period_payments_header",
                total=_fmt_money(ledger.payments_total),
                currency=cur,
            ),
        )
        for p in ledger.payments:
            if (p.paid_on.year, p.paid_on.month) != (ledger.year, ledger.month):
                lines.append(
                    t(
                        "period_payment_row_late",
                        date=p.paid_on.isoformat(),
                        amount=_fmt_money(p.amount),
                        paid_month=_ru_month(p.paid_on.month),
                        paid_year=p.paid_on.year,
                        currency=cur,
                    ),
                )
            else:
                lines.append(
                    t(
                        "period_payment_row",
                        date=p.paid_on.isoformat(),
                        amount=_fmt_money(p.amount),
                        note=p.note or "—",
                        currency=cur,
                    ),
                )
    else:
        lines.append("")
        lines.append(t("period_no_payments"))

    # Summary.
    lines.append("")
    lines.append(
        t("period_received", received=_fmt_money(ledger.received_total), currency=cur),
    )
    remaining = ledger.remaining
    if remaining is not None:
        lines.append(
            t("period_remaining", remaining=_fmt_money(remaining), currency=cur),
        )

    status = ledger.status
    if status == "pending":
        lines.append(t("period_status_pending"))
    elif status == "partial":
        lines.append(t("period_status_partial"))
    elif status == "settled":
        lines.append(t("period_status_settled"))
    elif status == "overpaid":
        assert remaining is not None
        lines.append(
            t("period_status_overpaid", overpaid=_fmt_money(-remaining), currency=cur),
        )
    else:  # unpriced
        lines.append(t("period_status_unpriced"))

    return "\n".join(lines)


def format_cashflow(
    entries: list[CashflowEntry], year: int, month: int, currency: str,
) -> str:
    if not entries:
        return t("cash_empty")
    total = sum((e.amount for e in entries), Decimal(0)).quantize(Decimal("0.01"))
    lines: list[str] = [
        t(
            "cash_header",
            month=_ru_month(month),
            year=year,
            total=_fmt_money(total),
            currency=currency,
        ),
    ]
    for e in entries:
        period = _period_label(e.period_year, e.period_month)
        key = "cash_row_advance" if e.kind == "advance" else "cash_row_payment"
        lines.append(
            t(
                key,
                date=e.day.isoformat(),
                amount=_fmt_money(e.amount),
                period=period,
                note=e.note or "—",
                currency=currency,
            ),
        )
    return "\n".join(lines)


def format_owed(ledgers: list[PeriodLedger], currency: str) -> str:
    if not ledgers:
        return t("owed_empty")
    lines: list[str] = [t("owed_header")]
    total = Decimal(0)
    for led in ledgers:
        remaining = led.remaining
        assert remaining is not None  # status filter excluded unpriced
        total += remaining
        period = _period_label(led.year, led.month)
        if led.status == "pending":
            lines.append(
                t(
                    "owed_row_pending",
                    period=period,
                    remaining=_fmt_money(remaining),
                    currency=currency,
                ),
            )
        else:  # partial
            lines.append(
                t(
                    "owed_row_partial",
                    period=period,
                    received=_fmt_money(led.received_total),
                    earnings=_fmt_money(led.earnings),
                    remaining=_fmt_money(remaining),
                    currency=currency,
                ),
            )
    lines.append("")
    lines.append(
        t(
            "owed_total",
            total=_fmt_money(total.quantize(Decimal("0.01"))),
            currency=currency,
        ),
    )
    return "\n".join(lines)


_PER_SHOW = "per:show:"   # per:show:YYYY-MM
_PER_OLDER = "per:older:"  # per:older:YYYY-MM (oldest shown in current page)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Return (year, month) shifted by ``delta`` months (negative = earlier)."""
    idx = year * 12 + (month - 1) + delta
    return idx // 12, (idx % 12) + 1


def period_picker_keyboard(
    anchor_year: int, anchor_month: int, page_size: int = 6,
) -> InlineKeyboardMarkup:
    """Inline keyboard listing ``page_size`` months ending at the anchor.

    Anchor = newest month on the page. The «◀ Раньше» button shifts the
    window back by ``page_size`` months.
    """
    months: list[tuple[int, int]] = []
    for i in range(page_size):
        y, m = _shift_month(anchor_year, anchor_month, -i)
        months.append((y, m))
    rows: list[list[InlineKeyboardButton]] = []
    # Two columns.
    for i in range(0, len(months), 2):
        row: list[InlineKeyboardButton] = []
        for y, m in months[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text=_period_label(y, m),
                    callback_data=f"{_PER_SHOW}{y}-{m:02d}",
                ),
            )
        rows.append(row)
    older_y, older_m = _shift_month(anchor_year, anchor_month, -page_size)
    rows.append(
        [
            InlineKeyboardButton(
                text=t("period_older_btn"),
                callback_data=f"{_PER_OLDER}{older_y}-{older_m:02d}",
            ),
        ],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_period(
    message: Message, db_user: User, year: int, month: int,
) -> None:
    tz = ZoneInfo(get_settings().timezone)
    async for session in get_session():
        ledger = await get_period_ledger(
            session, user=db_user, year=year, month=month, tz=tz,
        )
    await message.answer(format_period(ledger, db_user))


@router.message(Command("period"))
async def cmd_period(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/period`` shows the month picker; ``/period YYYY-MM`` renders directly."""
    if db_user is None:
        return
    tz = ZoneInfo(get_settings().timezone)
    if command.args:
        ym = parse_year_month(command.args)
        if ym is None:
            await message.answer(t("month_format"))
            return
        year, month = ym
        await _send_period(message, db_user, year, month)
        return
    year, month = _current_year_month(tz)
    await message.answer(
        t("period_pick_prompt"),
        reply_markup=period_picker_keyboard(year, month),
    )


@router.callback_query(F.data.startswith(_PER_SHOW))
async def cb_period_show(
    query: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    ym = parse_year_month(query.data[len(_PER_SHOW):])
    if ym is None:
        await query.answer()
        return
    year, month = ym
    if isinstance(query.message, Message):
        await _send_period(query.message, db_user, year, month)
    await query.answer()


@router.callback_query(F.data.startswith(_PER_OLDER))
async def cb_period_older(
    query: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or query.data is None:
        await query.answer()
        return
    ym = parse_year_month(query.data[len(_PER_OLDER):])
    if ym is None:
        await query.answer()
        return
    year, month = ym
    if isinstance(query.message, Message):
        with contextlib.suppress(Exception):
            await query.message.edit_reply_markup(
                reply_markup=period_picker_keyboard(year, month),
            )
    await query.answer()


@router.message(Command("cash"))
async def cmd_cash(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """``/cash`` (current month) or ``/cash YYYY-MM``."""
    if db_user is None:
        return
    tz = ZoneInfo(get_settings().timezone)
    if command.args:
        ym = parse_year_month(command.args)
        if ym is None:
            await message.answer(t("month_format"))
            return
        year, month = ym
    else:
        year, month = _current_year_month(tz)
    first_day, last_day = month_bounds(year, month)
    async for session in get_session():
        entries = await list_cashflow(
            session, user=db_user, start=first_day, end=last_day,
        )
    await message.answer(format_cashflow(entries, year, month, db_user.currency))


@router.message(Command("owed"))
async def cmd_owed(message: Message, db_user: User | None = None) -> None:
    """``/owed`` — periods still unpaid or partial (last 12 months)."""
    if db_user is None:
        return
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    async for session in get_session():
        ledgers = await list_open_periods(
            session, user=db_user, tz=tz, today=today,
        )
    await message.answer(format_owed(ledgers, db_user.currency))
