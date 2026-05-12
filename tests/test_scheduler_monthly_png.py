"""Phase 7.5: monthly digest PNG attachment wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.bot import scheduler_runner
from src.core.models import User


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TZ = ZoneInfo("Europe/Warsaw")


@dataclass
class _Settings:
    timezone: str = "Europe/Warsaw"
    daily_digest_hour: int = 9
    daily_digest_enabled: bool = True
    owner_tg_id: int = 555


class _Bot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.documents: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kw: object) -> None:
        self.messages.append((chat_id, text))

    async def send_document(
        self, chat_id: int, document: object, **_kw: object,
    ) -> None:
        filename = getattr(document, "filename", "")
        self.documents.append((chat_id, filename))


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    scheduler_runner._last_monthly_digest_period = None


@pytest.mark.asyncio
async def test_monthly_digest_attaches_png_on_day_one(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed owner user matching settings.owner_tg_id.
    user = User(
        tg_id=555, name="Иван", locale="ru",
        currency="PLN", role="worker", hourly_rate=Decimal("30.00"),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    session.add(user)
    await session.commit()

    async def fake_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(scheduler_runner, "get_session", fake_get_session)

    async def fake_text(*_a: object, **_kw: object) -> str:
        return "monthly digest body"

    monkeypatch.setattr(scheduler_runner, "build_monthly_digest", fake_text)

    async def fake_report_data(*_a: object, **_kw: object) -> object:
        return object()  # PNG builder is also stubbed.

    monkeypatch.setattr(scheduler_runner, "get_report_data", fake_report_data)

    def fake_png(_data: object, _user: User) -> BytesIO:
        return BytesIO(b"\x89PNG\r\n\x1a\nFAKE")

    monkeypatch.setattr(scheduler_runner, "build_report_png", fake_png)

    # Freeze now to day-1 in May 2026 at the digest hour.
    when = datetime(2026, 5, 1, 9, 0, tzinfo=_TZ)
    monkeypatch.setattr(scheduler_runner, "datetime", _StubDatetime(when))

    bot = _Bot()
    await scheduler_runner._maybe_send_monthly_digest(bot, _Settings())  # type: ignore[arg-type]

    assert bot.messages == [(555, "monthly digest body")]
    assert len(bot.documents) == 1
    chat_id, filename = bot.documents[0]
    assert chat_id == 555
    assert filename == "report_2026-04.png"


@pytest.mark.asyncio
async def test_monthly_digest_skips_when_not_day_one(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(scheduler_runner, "get_session", fake_get_session)
    when = datetime(2026, 5, 12, 9, 0, tzinfo=_TZ)
    monkeypatch.setattr(scheduler_runner, "datetime", _StubDatetime(when))

    bot = _Bot()
    await scheduler_runner._maybe_send_monthly_digest(bot, _Settings())  # type: ignore[arg-type]
    assert bot.messages == []
    assert bot.documents == []


class _StubDatetime:
    """Tiny shim so ``datetime.now(tz=...)`` inside scheduler_runner returns
    a fixed moment without affecting other modules' ``datetime`` usage."""

    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        if tz is None:
            return self._fixed
        return self._fixed.astimezone(tz)

    def __getattr__(self, name: str) -> object:
        return getattr(datetime, name)
