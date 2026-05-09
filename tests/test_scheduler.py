"""Tests for the scheduler service auto-close and reminder logic."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from src.services.scheduler import auto_close_shift, mark_reminder_sent

from tests.conftest import FakeShift

_UTC = ZoneInfo("UTC")


@pytest.mark.asyncio
async def test_auto_close_sets_end_at_and_flag() -> None:
    shift = FakeShift(
        id=1,
        start_at=datetime(2026, 5, 8, 0, 0, tzinfo=_UTC),
        end_at=None,
    )
    session = AsyncMock()
    now = datetime(2026, 5, 8, 14, 0, tzinfo=_UTC)

    result = await auto_close_shift(session, shift, now=now)  # type: ignore[arg-type]

    assert result.end_at == now
    assert result.auto_closed is True
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_close_uses_current_time_when_now_omitted() -> None:
    shift = FakeShift(id=1, end_at=None)
    session = AsyncMock()
    before = datetime.now(tz=_UTC)

    result = await auto_close_shift(session, shift)  # type: ignore[arg-type]

    after = datetime.now(tz=_UTC)
    assert result.end_at is not None
    assert before <= result.end_at <= after
    assert result.auto_closed is True


@pytest.mark.asyncio
async def test_mark_reminder_sets_timestamp() -> None:
    shift = FakeShift(id=1, reminder_sent_at=None)
    session = AsyncMock()
    now = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)

    result = await mark_reminder_sent(session, shift, now=now)  # type: ignore[arg-type]

    assert result.reminder_sent_at == now
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_reminder_uses_current_time_when_now_omitted() -> None:
    shift = FakeShift(id=1, reminder_sent_at=None)
    session = AsyncMock()
    before = datetime.now(tz=_UTC)

    result = await mark_reminder_sent(session, shift)  # type: ignore[arg-type]

    after = datetime.now(tz=_UTC)
    assert result.reminder_sent_at is not None
    assert before <= result.reminder_sent_at <= after


def test_reminder_window_boundaries() -> None:
    """Sanity check on threshold/cutoff math used by find_shifts_needing_reminder."""
    now = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)
    threshold_hours = 8
    max_hours = 14

    threshold = now - timedelta(hours=threshold_hours)
    auto_close_cutoff = now - timedelta(hours=max_hours)

    # A shift started 9h ago is past threshold (8h) but not past auto-close (14h)
    started_9h_ago = now - timedelta(hours=9)
    assert started_9h_ago <= threshold
    assert started_9h_ago > auto_close_cutoff

    # A shift started 15h ago is past auto-close cutoff -> NOT a reminder candidate
    started_15h_ago = now - timedelta(hours=15)
    assert started_15h_ago <= auto_close_cutoff

    # A shift started 4h ago has not yet crossed threshold
    started_4h_ago = now - timedelta(hours=4)
    assert started_4h_ago > threshold
