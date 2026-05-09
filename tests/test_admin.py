"""Tests for admin handler helpers."""

from decimal import Decimal

from src.bot.handlers.admin import _parse_rate


def test_parse_rate_dot_separator() -> None:
    assert _parse_rate("50.5") == Decimal("50.50")


def test_parse_rate_comma_separator() -> None:
    assert _parse_rate("50,5") == Decimal("50.50")


def test_parse_rate_integer() -> None:
    assert _parse_rate("60") == Decimal("60.00")


def test_parse_rate_zero_allowed() -> None:
    assert _parse_rate("0") == Decimal("0.00")


def test_parse_rate_negative_rejected() -> None:
    assert _parse_rate("-10") is None


def test_parse_rate_garbage_rejected() -> None:
    assert _parse_rate("abc") is None
    assert _parse_rate("") is None
