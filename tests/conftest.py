"""Test fixtures."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

_UTC = ZoneInfo("UTC")
_WARSAW = ZoneInfo("Europe/Warsaw")


def _utc_default() -> datetime:
    return datetime(2026, 1, 1, tzinfo=_UTC)


@dataclass
class FakeUser:
    id: int = 1
    tg_id: int = 123456789
    name: str = "Test User"
    locale: str = "ru"
    hourly_rate: Decimal | None = Decimal("50.00")
    created_at: datetime = field(default_factory=_utc_default)


@dataclass
class FakeSite:
    id: int = 1
    user_id: int = 1
    name: str = "Test Site"
    polygon: object = None
    hourly_rate: Decimal | None = Decimal("60.00")
    archived_at: datetime | None = None
    created_at: datetime = field(default_factory=_utc_default)


@dataclass
class FakeShift:
    id: int = 0
    user_id: int = 1
    site_id: int | None = 1
    start_at: datetime = field(
        default_factory=lambda: datetime(2026, 5, 8, 8, 0, tzinfo=_WARSAW),
    )
    end_at: datetime | None = None
    start_location: object = None
    end_location: object = None
    start_photo_file_id: str | None = None
    end_photo_file_id: str | None = None
    note: str | None = None
    work_type: str | None = None
    auto_closed: bool = False
    reminder_sent_at: datetime | None = None
    created_at: datetime = field(default_factory=_utc_default)


@pytest.fixture
def tz_warsaw() -> ZoneInfo:
    return _WARSAW


@pytest.fixture
def sample_user() -> FakeUser:
    return FakeUser()


@pytest.fixture
def sample_site() -> FakeSite:
    return FakeSite()


@pytest.fixture
def sample_shifts(tz_warsaw: ZoneInfo) -> list[FakeShift]:
    """Create sample shifts for testing."""
    return [
        FakeShift(
            id=1,
            start_at=datetime(2026, 5, 8, 8, 0, tzinfo=tz_warsaw),
            end_at=datetime(2026, 5, 8, 16, 0, tzinfo=tz_warsaw),
            note="Foundation work",
            work_type="concrete",
        ),
        FakeShift(
            id=2,
            start_at=datetime(2026, 5, 8, 23, 30, tzinfo=tz_warsaw),
            end_at=datetime(2026, 5, 9, 0, 30, tzinfo=tz_warsaw),
            work_type="welding",
        ),
    ]
