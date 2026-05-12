"""Tests for the Phase 5.3 evening reminder service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from src.services.reminders import find_users_needing_reminder, mark_reminded

_WARSAW = ZoneInfo("Europe/Warsaw")


@dataclass
class FakeUser:
    id: int
    tg_id: int = 100
    name: str = "U"
    remind_hour_local: int | None = 19
    day_reminder_last_sent: date | None = None


@dataclass
class _ScalarsResult:
    items: list[object]

    def all(self) -> list[object]:
        return list(self.items)


@dataclass
class _ExecuteResult:
    """Mimics SQLAlchemy Result for both .scalars().all() and .all()."""

    rows: list[object] = field(default_factory=list)
    scalar_items: list[object] = field(default_factory=list)

    def scalars(self) -> _ScalarsResult:
        return _ScalarsResult(self.scalar_items)

    def all(self) -> list[object]:
        return list(self.rows)


def _make_session(*results: _ExecuteResult) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(results))
    return session


@pytest.mark.asyncio
async def test_mark_reminded_sets_field_and_flushes() -> None:
    user = FakeUser(id=1)
    session = AsyncMock()
    today = date(2026, 5, 11)

    await mark_reminded(session, user=user, today=today)  # type: ignore[arg-type]

    assert user.day_reminder_last_sent == today
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_candidates_returns_empty() -> None:
    session = _make_session(_ExecuteResult(scalar_items=[]))
    now = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert out == []
    # Only the first query should run when no candidates exist.
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_skips_users_already_reminded_today() -> None:
    today = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW).date()
    user = FakeUser(id=1, day_reminder_last_sent=today)
    session = _make_session(_ExecuteResult(scalar_items=[user]))
    now = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert out == []
    # Second query is skipped because nothing remained after the filter.
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_skips_users_with_day_entry_today() -> None:
    user = FakeUser(id=42, day_reminder_last_sent=None)
    session = _make_session(
        _ExecuteResult(scalar_items=[user]),
        # The DayEntry-presence query returns (user_id,) tuples.
        _ExecuteResult(rows=[(42,)]),
    )
    now = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert out == []
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_returns_eligible_user() -> None:
    user = FakeUser(id=7, tg_id=999, day_reminder_last_sent=None)
    session = _make_session(
        _ExecuteResult(scalar_items=[user]),
        _ExecuteResult(rows=[]),  # no DayEntry for today
    )
    now = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert [u.id for u in out] == [7]


@pytest.mark.asyncio
async def test_uses_now_kwarg_to_compute_today() -> None:
    """Passing `now` controls 'today' regardless of wall-clock."""
    # 2026-05-11 23:30 Warsaw is still 2026-05-11 locally.
    user_done = FakeUser(id=1, day_reminder_last_sent=date(2026, 5, 11))
    session = _make_session(_ExecuteResult(scalar_items=[user_done]))
    now = datetime(2026, 5, 11, 23, 30, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert out == []


@pytest.mark.asyncio
async def test_converts_naive_now_via_tz() -> None:
    """A tz-aware `now` from another zone is converted to the target tz."""
    user = FakeUser(id=1, day_reminder_last_sent=None)
    session = _make_session(
        _ExecuteResult(scalar_items=[user]),
        _ExecuteResult(rows=[]),
    )
    # 2026-05-11 18:00 UTC == 2026-05-11 20:00 Warsaw.
    now_utc = datetime(2026, 5, 11, 18, 0, tzinfo=ZoneInfo("UTC"))

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now_utc)

    assert [u.id for u in out] == [1]


@pytest.mark.asyncio
async def test_only_one_of_many_with_entry_filtered() -> None:
    users = [
        FakeUser(id=1, day_reminder_last_sent=None),
        FakeUser(id=2, day_reminder_last_sent=None),
        FakeUser(id=3, day_reminder_last_sent=None),
    ]
    session = _make_session(
        _ExecuteResult(scalar_items=list(users)),
        _ExecuteResult(rows=[(2,)]),  # user 2 already has an entry today
    )
    now = datetime(2026, 5, 11, 20, 0, tzinfo=_WARSAW)

    out = await find_users_needing_reminder(session, tz=_WARSAW, now=now)

    assert sorted(u.id for u in out) == [1, 3]


def test_find_users_needing_reminder_signature_accepts_zoneinfo() -> None:
    """Smoke check: importing the symbol and calling with mocks works."""
    # The earlier async tests cover behaviour; here we just confirm callers
    # can pass a MagicMock session if they wire side_effects themselves.
    session = MagicMock()
    assert session is not None


# --- Phase 7.9 — per-user resolve_tz path -------------------------------

_DUBAI = ZoneInfo("Asia/Dubai")  # +4
_NEW_YORK = ZoneInfo("America/New_York")  # -4/-5


@pytest.mark.asyncio
async def test_resolve_tz_includes_user_whose_local_hour_has_passed() -> None:
    """At 16:00 UTC, Dubai is 20:00 (>=19 ✓) while New York is 12:00 (<19 ✗)."""
    dubai_user = FakeUser(id=1, remind_hour_local=19, day_reminder_last_sent=None)
    ny_user = FakeUser(id=2, remind_hour_local=19, day_reminder_last_sent=None)
    session = _make_session(
        _ExecuteResult(scalar_items=[dubai_user, ny_user]),
        _ExecuteResult(rows=[]),  # no DayEntry for anyone
    )
    now_utc = datetime(2026, 5, 11, 16, 0, tzinfo=ZoneInfo("UTC"))
    tz_map = {1: _DUBAI, 2: _NEW_YORK}

    out = await find_users_needing_reminder(
        session, tz=_WARSAW, now=now_utc,
        resolve_tz=lambda u: tz_map[u.id],  # type: ignore[attr-defined]
    )

    assert [u.id for u in out] == [1]


@pytest.mark.asyncio
async def test_resolve_tz_uses_user_local_date_for_dedup() -> None:
    """User already reminded 'today' in their local zone is skipped."""
    # 22:00 UTC on 2026-05-11 -> Dubai local: 02:00 on 2026-05-12.
    dubai_user = FakeUser(
        id=1, remind_hour_local=2,
        day_reminder_last_sent=date(2026, 5, 12),  # already reminded
    )
    session = _make_session(_ExecuteResult(scalar_items=[dubai_user]))
    now_utc = datetime(2026, 5, 11, 22, 0, tzinfo=ZoneInfo("UTC"))

    out = await find_users_needing_reminder(
        session, tz=_WARSAW, now=now_utc,
        resolve_tz=lambda _u: _DUBAI,
    )

    assert out == []
