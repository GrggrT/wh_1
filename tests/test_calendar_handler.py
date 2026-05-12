"""Phase 6.6: calendar handler — pure helpers and keyboard layout.

The interactive flows (FSM, callbacks) are covered indirectly by the
service-layer tests for day_entries, advances, and salary_payments.
Here we just verify the pure month-math helpers and that key callback
data fits the Telegram 64-byte limit.
"""

from __future__ import annotations

from datetime import date

from src.bot.handlers.calendar import (
    _RU_MONTHS,
    _hours_picker_keyboard,
    _next_month,
    _period_keyboard,
    _prev_month,
)


def test_prev_month_rolls_over_january() -> None:
    assert _prev_month(2026, 1) == (2025, 12)


def test_prev_month_normal() -> None:
    assert _prev_month(2026, 5) == (2026, 4)


def test_next_month_rolls_over_december() -> None:
    assert _next_month(2026, 12) == (2027, 1)


def test_next_month_normal() -> None:
    assert _next_month(2026, 5) == (2026, 6)


def test_ru_months_has_twelve_entries() -> None:
    assert len(_RU_MONTHS) == 12


def test_period_keyboard_offers_prev_current_prev2_anchored_to_paid_on() -> None:
    """For a payment on 2026-05-12, the period quick-picks should be
    April 2026 (prev), May 2026 (current), March 2026 (prev-prev)."""
    kb = _period_keyboard(date(2026, 5, 12))
    # 3 period rows + 1 back row.
    assert len(kb.inline_keyboard) == 4
    cb_first = kb.inline_keyboard[0][0].callback_data or ""
    cb_second = kb.inline_keyboard[1][0].callback_data or ""
    cb_third = kb.inline_keyboard[2][0].callback_data or ""
    assert cb_first.endswith(":2026-04")
    assert cb_second.endswith(":2026-05")
    assert cb_third.endswith(":2026-03")


def test_period_keyboard_rolls_over_january_paid_on() -> None:
    """Payment in Jan 2026 → prev = Dec 2025, prev-prev = Nov 2025."""
    kb = _period_keyboard(date(2026, 1, 10))
    cb_first = kb.inline_keyboard[0][0].callback_data or ""
    cb_third = kb.inline_keyboard[2][0].callback_data or ""
    assert cb_first.endswith(":2025-12")
    assert cb_third.endswith(":2025-11")


def test_callback_data_fits_telegram_64_byte_limit() -> None:
    """Telegram rejects callback_data over 64 bytes. Verify our longest
    payloads (period + paid_on combined) stay well under."""
    kb = _period_keyboard(date(2026, 12, 31))
    for row in kb.inline_keyboard:
        for btn in row:
            assert btn.callback_data is not None
            assert len(btn.callback_data.encode("utf-8")) <= 64


def test_hours_picker_includes_back_button() -> None:
    kb = _hours_picker_keyboard(date(2026, 5, 12))
    last_row = kb.inline_keyboard[-1]
    assert len(last_row) == 1
    cb = last_row[0].callback_data or ""
    assert cb.startswith("cal:day:")
