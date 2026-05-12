"""Phase 6.2: DB-integration tests against an in-memory aiosqlite engine.

We selectively create the SQLAlchemy tables that do NOT depend on
PostgreSQL-only types (PostGIS Geography, JSONB). That gives us real SQL
roundtrips for the services that drive the simple-mode product:

- app_settings: read/upsert/toggle
- day_entries: upsert / get / list_recent / smart_suggest input
- advances: record + list

Site/Shift/AuditLog are intentionally excluded — they require PostGIS /
JSONB which aiosqlite cannot emulate without external extensions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.core.models import Advance, AppSettings, Crew, DayEntry, User
from src.services.advances import list_advances, record_advance
from src.services.app_settings import (
    SettingsSnapshot,
    get_settings,
    toggle,
)
from src.services.day_entries import (
    DAY_OFF,
    get_day_entry,
    list_recent_entries,
    upsert_day_entry,
)


# sqlite uses "INTEGER PRIMARY KEY" as the rowid alias for autoincrement;
# BIGINT is not an alias, so models declared with BigInteger PK won't
# auto-fill on sqlite. For the test backend only, rewrite BIGINT -> INTEGER.
@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES_FOR_TESTS = [
    Crew.__table__,
    User.__table__,
    DayEntry.__table__,
    Advance.__table__,
    AppSettings.__table__,
]


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory sqlite with our subset of tables, one AsyncSession."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        # Create only the PG-free tables. FK refs to missing tables (e.g.
        # DayEntry.site_id -> sites.id) are accepted by sqlite as long as the
        # foreign_keys pragma is off (default).
        for table in _TABLES_FOR_TESTS:
            await conn.run_sync(table.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_user(session: AsyncSession, *, tg_id: int = 111) -> User:
    user = User(tg_id=tg_id, name="Test Worker", hourly_rate=Decimal("50.00"))
    session.add(user)
    await session.flush()
    return user


# ---- app_settings ---------------------------------------------------------


async def _seed_app_settings(session: AsyncSession) -> None:
    """Seed app_settings row with explicit defaults.

    The production server_default values are PostgreSQL-side; sqlite stores
    them as text literals, so we set them explicitly for cross-dialect
    determinism in tests.
    """
    row = AppSettings(
        id=1,
        sites_enabled=False,
        crews_enabled=False,
        geofence_enabled=False,
        legacy_clock_inout_enabled=True,
    )
    session.add(row)
    await session.flush()


async def test_app_settings_autocreates_row_on_first_read(
    session: AsyncSession,
) -> None:
    snap = await get_settings(session)
    # The service creates the row when missing; type roundtrips correctly.
    assert isinstance(snap, SettingsSnapshot)


async def test_app_settings_toggle_flips_persisted_value(
    session: AsyncSession,
) -> None:
    await _seed_app_settings(session)
    before = await get_settings(session)
    new_snap = await toggle(session, "crews_enabled")
    await session.commit()
    assert before.crews_enabled is False
    assert new_snap.crews_enabled is True
    again = await get_settings(session)
    assert again.crews_enabled is True


async def test_app_settings_toggle_rejects_unknown_key(
    session: AsyncSession,
) -> None:
    with pytest.raises(ValueError):
        await toggle(session, "nope_not_a_real_toggle")


# ---- day_entries ----------------------------------------------------------


async def test_day_entries_upsert_creates_then_updates(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    today = date(2026, 5, 11)
    entry, created = await upsert_day_entry(
        session, user_id=user.id, day=today, hours=Decimal("8"),
    )
    assert created is True
    assert entry.hours == Decimal("8")

    entry2, created2 = await upsert_day_entry(
        session, user_id=user.id, day=today, hours=Decimal("9.5"),
    )
    assert created2 is False
    assert entry2.id == entry.id
    assert entry2.hours == Decimal("9.5")


async def test_day_entries_day_off_roundtrips(session: AsyncSession) -> None:
    user = await _seed_user(session)
    today = date(2026, 5, 11)
    entry, _ = await upsert_day_entry(
        session, user_id=user.id, day=today, hours=DAY_OFF,
    )
    assert entry.hours == DAY_OFF

    fetched = await get_day_entry(session, user_id=user.id, day=today)
    assert fetched is not None
    assert fetched.hours == DAY_OFF


async def test_list_recent_entries_filters_window_and_orders(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    # Use real today so the service's date.today() window matches the seeded
    # entries; otherwise the test becomes calendar-sensitive.
    today = date.today()
    for offset in range(0, 20):
        await upsert_day_entry(
            session,
            user_id=user.id,
            day=today - timedelta(days=offset),
            hours=Decimal("8"),
        )
    await session.commit()

    recent = await list_recent_entries(session, user_id=user.id, days=14)
    assert len(recent) == 14
    # Newest first.
    assert recent[0].day == today
    assert recent[-1].day == today - timedelta(days=13)


async def test_list_recent_entries_only_own_user(
    session: AsyncSession,
) -> None:
    a = await _seed_user(session, tg_id=1)
    b = await _seed_user(session, tg_id=2)
    today = date.today()
    await upsert_day_entry(session, user_id=a.id, day=today, hours=Decimal("8"))
    await upsert_day_entry(session, user_id=b.id, day=today, hours=Decimal("4"))
    await session.commit()

    rows_a = await list_recent_entries(session, user_id=a.id, days=7)
    assert len(rows_a) == 1
    assert rows_a[0].hours == Decimal("8")


# ---- advances -------------------------------------------------------------


async def test_record_advance_and_list_filters_by_range(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    foreman = await _seed_user(session, tg_id=222)
    await record_advance(
        session,
        user_id=user.id,
        amount=Decimal("100"),
        recorded_by_id=foreman.id,
        day=date(2026, 5, 5),
        note="materials",
    )
    await record_advance(
        session,
        user_id=user.id,
        amount=Decimal("250"),
        recorded_by_id=foreman.id,
        day=date(2026, 4, 20),
    )
    await session.commit()

    rows = await list_advances(
        session,
        user_id=user.id,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )
    assert len(rows) == 1
    assert rows[0].amount == Decimal("100")
    assert rows[0].note == "materials"
