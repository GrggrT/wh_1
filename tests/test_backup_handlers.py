"""Phase 7.1 / 7.8: integration tests for /export_archive and /restore.

These exercise the bot handlers end-to-end against an aiosqlite session
via monkeypatched ``get_session`` — no real Telegram is involved. The
goal is to lock down the wiring between FSM transitions, file handling,
and the restore/archive services.
"""
# ruff: noqa: ANN401, N814

from __future__ import annotations

import zipfile
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.bot.handlers import backup as backup_mod
from src.bot.handlers import report as report_mod
from src.core.config import Settings
from src.core.models import (
    Advance,
    CloudBackup,
    Crew,
    DayEntry,
    SalaryPayment,
    ShareToken,
    User,
)
from src.services import accounting as accounting_module
from src.services import backup_cloud as backup_cloud_mod
from src.services.advances import SalaryBreakdown
from src.services.reports.backup import build_backup_xlsx
from src.services.share_backup import issue_share_token


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES = [
    Crew.__table__,
    User.__table__,
    DayEntry.__table__,
    Advance.__table__,
    SalaryPayment.__table__,
    ShareToken.__table__,
    CloudBackup.__table__,
]


def _stub_compute_salary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass legacy Shift/Site queries (those tables aren't created)."""
    from zoneinfo import ZoneInfo as _ZI

    async def fake(
        _session: AsyncSession, *, user: User, year: int, month: int,
        tz: _ZI,  # noqa: ARG001
    ) -> SalaryBreakdown:
        return SalaryBreakdown(
            user_id=user.id, year=year, month=month,
            day_entries_hours=Decimal(0),
            day_entries_earnings=None,
            shifts_hours=Decimal(0),
            shifts_earnings=None,
            advances_total=Decimal(0),
            net_payable=None,
        )
    monkeypatch.setattr(accounting_module, "compute_salary", fake)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        for table in _TABLES:
            await conn.run_sync(table.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_user(session: AsyncSession) -> User:
    user = User(
        tg_id=100, name="Worker",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    session.add(user)
    await session.flush()
    return user


class _FakeMessage:
    def __init__(self) -> None:
        self.answers: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []

    async def answer(
        self, text: str, reply_markup: Any | None = None, **_: Any,
    ) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})

    async def answer_document(
        self, document: Any, caption: str | None = None, **_: Any,
    ) -> None:
        self.documents.append({"document": document, "caption": caption})

    async def edit_reply_markup(self, reply_markup: Any | None = None) -> None:
        return None


class _FakeDocument:
    def __init__(self, file_id: str, file_name: str, file_size: int) -> None:
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size


class _FakeFile:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path


class _FakeBot:
    """Returns pre-staged bytes for ``download_file``."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def get_file(self, _file_id: str) -> _FakeFile:
        return _FakeFile("/tmp/test.xlsx")

    async def download_file(
        self, _path: str, destination: BytesIO,
    ) -> None:
        destination.write(self._payload)


class _FakeFSM:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.state: Any = None

    async def set_state(self, state: Any) -> None:
        self.state = state

    async def update_data(self, **kw: Any) -> None:
        self._data.update(kw)

    async def get_data(self) -> dict[str, Any]:
        return dict(self._data)

    async def clear(self) -> None:
        self._data.clear()
        self.state = None


class _FakeCallback:
    def __init__(self, data: str, message: _FakeMessage) -> None:
        self.data = data
        self.message = message
        self.answered = False

    async def answer(self, *_a: Any, **_kw: Any) -> None:
        self.answered = True


def _patch_get_session(monkeypatch: pytest.MonkeyPatch, session: AsyncSession,
                       *modules: Any) -> None:
    """Make each module's ``get_session`` yield ``session`` exactly once."""

    async def _fake() -> AsyncIterator[AsyncSession]:
        yield session

    for mod in modules:
        monkeypatch.setattr(mod, "get_session", _fake)


def _patch_message_class(monkeypatch: pytest.MonkeyPatch, *modules: Any) -> None:
    """Replace ``Message`` in handler modules so ``isinstance`` accepts fakes."""
    for mod in modules:
        monkeypatch.setattr(mod, "Message", _FakeMessage)


# ---------------------------------------------------------------------
# /export_archive
# ---------------------------------------------------------------------


async def test_export_archive_emits_zip_with_three_artifacts(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    session.add(DayEntry(
        user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    ))
    await session.commit()

    _patch_get_session(monkeypatch, session, report_mod)
    _stub_compute_salary(monkeypatch)

    msg = _FakeMessage()

    class _Cmd:
        args = "2"

    await report_mod.cmd_export_archive(msg, _Cmd(), db_user=user)  # type: ignore[arg-type]

    assert len(msg.documents) == 1
    doc = msg.documents[0]["document"]
    # BufferedInputFile carries the raw bytes via .data
    raw = doc.data
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = set(zf.namelist())
    assert any(n.endswith(".xlsx") for n in names)
    assert any(n.endswith(".pdf") for n in names)
    assert any(n.endswith(".png") for n in names)


# ---------------------------------------------------------------------
# /restore — confirm flow round-trip
# ---------------------------------------------------------------------


async def test_restore_confirm_round_trip_inserts_rows(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)

    # Backup payload contains one new day entry.
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    )]
    payload = build_backup_xlsx(
        user, days, [], [], today=date(2026, 5, 12),
    ).getvalue()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    msg.document = _FakeDocument(  # type: ignore[attr-defined]
        file_id="abc123", file_name="wh1_backup_1.xlsx", file_size=len(payload),
    )
    bot = _FakeBot(payload)

    # Drive: document arrival -> preview/confirm prompt.
    await backup_mod.msg_restore_document(
        msg,  # type: ignore[arg-type]
        fsm,  # type: ignore[arg-type]
        bot,  # type: ignore[arg-type]
        db_user=user,
    )

    assert fsm.state == backup_mod.RestoreFlow.awaiting_confirm
    assert fsm._data.get("file_id") == "abc123"
    assert any("Дней: <b>1</b>" in a["text"] for a in msg.answers)

    # Drive: confirm callback -> apply.
    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="restore:apply", message=cb_msg)
    await backup_mod.cb_restore_apply(
        cb,  # type: ignore[arg-type]
        fsm,  # type: ignore[arg-type]
        bot,  # type: ignore[arg-type]
        db_user=user,
    )

    assert cb.answered
    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].day == date(2026, 5, 1)
    assert fsm.state is None  # FSM cleared


async def test_restore_cancel_callback_clears_without_writes(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 2),
        hours=Decimal("6.00"), note=None,
    )]
    payload = build_backup_xlsx(
        user, days, [], [], today=date(2026, 5, 12),
    ).getvalue()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    msg.document = _FakeDocument(  # type: ignore[attr-defined]
        "fid", "bk.xlsx", len(payload),
    )
    bot = _FakeBot(payload)

    await backup_mod.msg_restore_document(
        msg, fsm, bot, db_user=user,  # type: ignore[arg-type]
    )
    assert fsm.state == backup_mod.RestoreFlow.awaiting_confirm

    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="restore:cancel", message=cb_msg)
    await backup_mod.cb_restore_cancel(
        cb, fsm,  # type: ignore[arg-type]
    )

    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert rows == []
    assert fsm.state is None


# ---------------------------------------------------------------------
# /restore_from — share-token confirm flow
# ---------------------------------------------------------------------


class _Cmd:
    def __init__(self, args: str) -> None:
        self.args = args


async def test_restore_from_preview_then_confirm_applies(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = User(
        tg_id=200, name="Src",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    dst = User(
        tg_id=201, name="Dst",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    session.add_all([src, dst])
    await session.flush()
    session.add(DayEntry(
        user_id=src.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    ))
    issued = await issue_share_token(session, source_user=src)
    await session.commit()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    await backup_mod.cmd_restore_from(
        msg, _Cmd(issued.token), fsm, db_user=dst,  # type: ignore[arg-type]
    )

    assert fsm.state == backup_mod.ShareRestoreFlow.awaiting_confirm
    assert fsm._data.get("share_token") == issued.token
    assert any("Дней: <b>1</b>" in a["text"] for a in msg.answers)

    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="share:apply", message=cb_msg)
    await backup_mod.cb_share_apply(
        cb, fsm, db_user=dst,  # type: ignore[arg-type]
    )
    assert cb.answered
    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == dst.id),
    )).scalars().all()
    assert len(rows) == 1
    assert fsm.state is None


async def test_restore_from_cancel_does_not_consume_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = User(
        tg_id=210, name="Src",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    dst = User(
        tg_id=211, name="Dst",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    session.add_all([src, dst])
    await session.flush()
    issued = await issue_share_token(session, source_user=src)
    await session.commit()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    await backup_mod.cmd_restore_from(
        msg, _Cmd(issued.token), fsm, db_user=dst,  # type: ignore[arg-type]
    )
    assert fsm.state == backup_mod.ShareRestoreFlow.awaiting_confirm

    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="share:cancel", message=cb_msg)
    await backup_mod.cb_share_cancel(
        cb, fsm,  # type: ignore[arg-type]
    )

    # Token should still be redeemable — peek-then-cancel must not consume.
    token_row = (await session.execute(
        select(ShareToken).where(ShareToken.token == issued.token),
    )).scalar_one()
    assert token_row.redeemed_at is None
    assert fsm.state is None


# ---------------------------------------------------------------------
# /restore_from_cloud — confirm flow
# ---------------------------------------------------------------------


def _cloud_settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        bot_token="t",
        owner_tg_id=1,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="srv-key",
        supabase_backups_bucket="backups",
    )


async def test_restore_from_cloud_preview_then_confirm_applies(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    )]
    payload = build_backup_xlsx(
        user, days, [], [], today=date(2026, 5, 12),
    ).getvalue()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)
    monkeypatch.setattr(backup_mod, "get_settings", _cloud_settings)
    monkeypatch.setattr(backup_mod, "cloud_storage_enabled", lambda _s: True)

    async def fake_fetch(
        _s: AsyncSession, *, key: str, settings: Settings,  # noqa: ARG001
    ) -> bytes:
        assert key == "k1"
        return payload

    monkeypatch.setattr(backup_mod, "fetch_cloud_backup", fake_fetch)
    monkeypatch.setattr(backup_cloud_mod, "fetch_cloud_backup", fake_fetch)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    await backup_mod.cmd_restore_from_cloud(
        msg, _Cmd("k1"), fsm, db_user=user,  # type: ignore[arg-type]
    )

    assert fsm.state == backup_mod.CloudRestoreFlow.awaiting_confirm
    assert fsm._data.get("cloud_key") == "k1"
    assert any("Дней: <b>1</b>" in a["text"] for a in msg.answers)

    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="cloud:apply", message=cb_msg)
    await backup_mod.cb_cloud_apply(
        cb, fsm, db_user=user,  # type: ignore[arg-type]
    )
    assert cb.answered
    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 1
    assert fsm.state is None


async def test_restore_from_cloud_cancel_does_not_apply(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    )]
    payload = build_backup_xlsx(
        user, days, [], [], today=date(2026, 5, 12),
    ).getvalue()

    _patch_get_session(monkeypatch, session, backup_mod)
    _patch_message_class(monkeypatch, backup_mod)
    monkeypatch.setattr(backup_mod, "get_settings", _cloud_settings)
    monkeypatch.setattr(backup_mod, "cloud_storage_enabled", lambda _s: True)

    async def fake_fetch(
        _s: AsyncSession, *, key: str, settings: Settings,  # noqa: ARG001
    ) -> bytes:
        return payload

    monkeypatch.setattr(backup_mod, "fetch_cloud_backup", fake_fetch)

    fsm = _FakeFSM()
    msg = _FakeMessage()
    await backup_mod.cmd_restore_from_cloud(
        msg, _Cmd("k1"), fsm, db_user=user,  # type: ignore[arg-type]
    )
    assert fsm.state == backup_mod.CloudRestoreFlow.awaiting_confirm

    cb_msg = _FakeMessage()
    cb = _FakeCallback(data="cloud:cancel", message=cb_msg)
    await backup_mod.cb_cloud_cancel(
        cb, fsm,  # type: ignore[arg-type]
    )

    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert rows == []
    assert fsm.state is None
