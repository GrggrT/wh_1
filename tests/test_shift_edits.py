"""Tests for shift edit service: parsing and per-field validation."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from src.services.shift_edits import (
    EDITABLE_FIELDS,
    parse_local_datetime,
)

_WARSAW = ZoneInfo("Europe/Warsaw")
_UTC = ZoneInfo("UTC")


def test_editable_fields_contains_expected() -> None:
    assert set(EDITABLE_FIELDS) == {"start", "end", "note", "work_type", "site"}


def test_parse_local_datetime_warsaw_to_utc() -> None:
    # Warsaw is UTC+2 in May (DST).
    dt = parse_local_datetime("2026-05-08 12:30", _WARSAW)
    assert dt.tzinfo == _UTC
    assert dt == datetime(2026, 5, 8, 10, 30, tzinfo=_UTC)


def test_parse_local_datetime_winter() -> None:
    # Warsaw is UTC+1 in January (no DST).
    dt = parse_local_datetime("2026-01-15 09:00", _WARSAW)
    assert dt == datetime(2026, 1, 15, 8, 0, tzinfo=_UTC)


def test_parse_local_datetime_invalid_format_raises() -> None:
    with pytest.raises(ValueError):
        parse_local_datetime("08.05.2026 12:30", _WARSAW)


def test_format_shift_summary_closed_same_day() -> None:
    from src.services.shift_edits import format_shift_summary

    from tests.conftest import FakeShift

    shift = FakeShift(
        id=7,
        start_at=datetime(2026, 5, 8, 8, 0, tzinfo=_WARSAW),
        end_at=datetime(2026, 5, 8, 16, 0, tzinfo=_WARSAW),
    )
    line = format_shift_summary(shift, "Foundation", _WARSAW)  # type: ignore[arg-type]
    assert "#7" in line
    assert "08.05 08:00" in line
    assert "16:00" in line
    assert "8.00 ч" in line
    assert "Foundation" in line


def test_format_shift_summary_open() -> None:
    from src.services.shift_edits import format_shift_summary

    from tests.conftest import FakeShift

    shift = FakeShift(
        id=9,
        start_at=datetime(2026, 5, 8, 8, 0, tzinfo=_WARSAW),
        end_at=None,
    )
    line = format_shift_summary(shift, None, _WARSAW)  # type: ignore[arg-type]
    assert "открыта" in line
    assert "#9" in line
