"""Phase 6.11e: tests for the natural-language intent parser."""

from __future__ import annotations

from datetime import date

from src.services.reports.parser import parse_intent

_TODAY = date(2026, 5, 12)


# --- empty / no-op ----------------------------------------------------


def test_parse_returns_none_for_empty_text() -> None:
    assert parse_intent("", today=_TODAY) is None
    assert parse_intent("   ", today=_TODAY) is None


def test_parse_returns_none_for_slash_commands() -> None:
    assert parse_intent("/report", today=_TODAY) is None
    assert parse_intent("/period 2026-05", today=_TODAY) is None


def test_parse_returns_none_for_unrelated_chatter() -> None:
    assert parse_intent("привет", today=_TODAY) is None
    assert parse_intent("спасибо!", today=_TODAY) is None


# --- forecast ---------------------------------------------------------


def test_forecast_keyword() -> None:
    intent = parse_intent("прогноз", today=_TODAY)
    assert intent is not None
    assert intent.kind == "forecast"


def test_forecast_phrase_до_конца_месяца() -> None:
    intent = parse_intent("сколько до конца месяца?", today=_TODAY)
    assert intent is not None
    assert intent.kind == "forecast"


# --- owed -------------------------------------------------------------


def test_owed_keyword() -> None:
    intent = parse_intent("долг", today=_TODAY)
    assert intent is not None
    assert intent.kind == "owed"


def test_owed_phrase_with_verb() -> None:
    intent = parse_intent("сколько должны?", today=_TODAY)
    assert intent is not None
    assert intent.kind == "owed"


# --- cash -------------------------------------------------------------


def test_cash_keyword_no_month() -> None:
    intent = parse_intent("касса", today=_TODAY)
    assert intent is not None
    assert intent.kind == "cash"
    assert intent.year is None and intent.month is None


def test_cash_keyword_with_month_name() -> None:
    intent = parse_intent("касса за апрель", today=_TODAY)
    assert intent is not None
    assert intent.kind == "cash"
    assert intent.year == 2026
    assert intent.month == 4


def test_cash_keyword_with_future_month_rolls_to_last_year() -> None:
    intent = parse_intent("касса за декабрь", today=_TODAY)
    assert intent is not None
    assert intent.kind == "cash"
    assert intent.year == 2025
    assert intent.month == 12


# --- period -----------------------------------------------------------


def test_month_name_alone_is_period() -> None:
    intent = parse_intent("май", today=_TODAY)
    assert intent is not None
    assert intent.kind == "period"
    assert intent.year == 2026
    assert intent.month == 5


def test_period_keyword_no_month() -> None:
    intent = parse_intent("период", today=_TODAY)
    assert intent is not None
    assert intent.kind == "period"
    assert intent.year is None and intent.month is None


def test_period_with_explicit_year() -> None:
    intent = parse_intent("за июль 2025", today=_TODAY)
    assert intent is not None
    assert intent.kind == "period"
    assert intent.year == 2025
    assert intent.month == 7


def test_report_keyword_with_month_name_becomes_period() -> None:
    """«Отчёт за май» is a single-month deep-dive — route to /period."""
    intent = parse_intent("отчёт за май", today=_TODAY)
    assert intent is not None
    assert intent.kind == "period"
    assert intent.month == 5


# --- report (rolling) -------------------------------------------------


def test_report_keyword_no_args_uses_default_window() -> None:
    intent = parse_intent("отчёт", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"
    assert intent.months is None  # caller uses DEFAULT_MONTHS


def test_report_with_n_months() -> None:
    intent = parse_intent("отчёт за 3 месяца", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"
    assert intent.months == 3


def test_report_with_short_form_месяцев() -> None:
    intent = parse_intent("сводка за 12 мес", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"
    assert intent.months == 12


def test_bare_n_months_implies_report() -> None:
    intent = parse_intent("за 6 месяцев", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"
    assert intent.months == 6


def test_report_n_out_of_range_drops_window() -> None:
    intent = parse_intent("отчёт за 50 месяцев", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"
    assert intent.months is None  # rejected → default


# --- case insensitivity ----------------------------------------------


def test_uppercase_input_still_parses() -> None:
    intent = parse_intent("ОТЧЁТ ЗА МАЙ", today=_TODAY)
    assert intent is not None
    assert intent.kind == "period"
    assert intent.month == 5


def test_yo_or_e_letter_variants() -> None:
    # Without the ё.
    intent = parse_intent("отчет", today=_TODAY)
    assert intent is not None
    assert intent.kind == "report"


# --- range ------------------------------------------------------------


def test_range_iso_pair() -> None:
    intent = parse_intent("2026-05-01 2026-05-15", today=_TODAY)
    assert intent is not None
    assert intent.kind == "range"
    assert intent.start == date(2026, 5, 1)
    assert intent.end == date(2026, 5, 15)


def test_range_iso_pair_with_separator() -> None:
    intent = parse_intent("с 2026-04-01 по 2026-04-15", today=_TODAY)
    assert intent is not None
    assert intent.kind == "range"
    assert intent.start == date(2026, 4, 1)
    assert intent.end == date(2026, 4, 15)


def test_range_day_range_with_month_name() -> None:
    intent = parse_intent("сколько за май 1-15", today=_TODAY)
    assert intent is not None
    assert intent.kind == "range"
    assert intent.start == date(2026, 5, 1)
    assert intent.end == date(2026, 5, 15)


def test_range_с_по_with_month_name() -> None:
    intent = parse_intent("с 1 по 15 мая", today=_TODAY)
    assert intent is not None
    assert intent.kind == "range"
    assert intent.start == date(2026, 5, 1)
    assert intent.end == date(2026, 5, 15)


def test_range_swap_if_reversed() -> None:
    intent = parse_intent("2026-05-15 2026-05-01", today=_TODAY)
    assert intent is not None
    assert intent.kind == "range"
    assert intent.start == date(2026, 5, 1)
    assert intent.end == date(2026, 5, 15)


def test_range_invalid_day_falls_through() -> None:
    """40 days in May → no range detected (day out of range)."""
    intent = parse_intent("с 1 по 40 мая", today=_TODAY)
    # Should not crash; either None or non-range intent is acceptable.
    if intent is not None:
        assert intent.kind != "range"
