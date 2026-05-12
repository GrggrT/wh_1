"""Phase 6.11e follow-up: nl_router dispatcher tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from src.bot.handlers import nl_router
from src.core.models import User


@dataclass
class _CallRecord:
    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text


def _user() -> User:
    return User(
        id=1, tg_id=999, name="Иван", locale="ru",
        currency="PLN", role="worker", hourly_rate=Decimal("30.00"),
    )


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[_CallRecord]:
    log: list[_CallRecord] = []

    async def _record(name: str) -> Any:  # noqa: ANN401
        async def fn(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
            log.append(_CallRecord(name=name, args=args, kwargs=kwargs))
        return fn

    # Patch each downstream handler.
    import asyncio
    monkeypatch.setattr(
        nl_router, "cmd_period", asyncio.run(_record("period")),
    )
    monkeypatch.setattr(
        nl_router, "cmd_cash", asyncio.run(_record("cash")),
    )
    monkeypatch.setattr(
        nl_router, "cmd_owed", asyncio.run(_record("owed")),
    )
    monkeypatch.setattr(
        nl_router, "cmd_report", asyncio.run(_record("report")),
    )
    return log


# --- skip conditions --------------------------------------------------


@pytest.mark.asyncio
async def test_skips_when_no_user(calls: list[_CallRecord]) -> None:
    msg = _FakeMessage("отчёт")
    await nl_router.nl_dispatch(msg, db_user=None)  # type: ignore[arg-type]
    assert calls == []


@pytest.mark.asyncio
async def test_skips_slash_commands(calls: list[_CallRecord]) -> None:
    msg = _FakeMessage("/report")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert calls == []


@pytest.mark.asyncio
async def test_skips_empty_text(calls: list[_CallRecord]) -> None:
    msg = _FakeMessage("")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert calls == []


@pytest.mark.asyncio
async def test_skips_unrecognized_phrase(calls: list[_CallRecord]) -> None:
    msg = _FakeMessage("привет!")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert calls == []


# --- dispatch ---------------------------------------------------------


@pytest.mark.asyncio
async def test_owed_phrase_routes_to_owed(calls: list[_CallRecord]) -> None:
    msg = _FakeMessage("долг")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert [c.name for c in calls] == ["owed"]


@pytest.mark.asyncio
async def test_cash_with_month_routes_to_cash(
    calls: list[_CallRecord],
) -> None:
    msg = _FakeMessage("касса за апрель")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert [c.name for c in calls] == ["cash"]
    cmd_obj = calls[0].args[1]
    # YYYY-MM string passed through.
    assert cmd_obj.args is not None
    assert cmd_obj.args.endswith("-04")


@pytest.mark.asyncio
async def test_report_with_n_months_passes_arg(
    calls: list[_CallRecord],
) -> None:
    msg = _FakeMessage("отчёт за 12 мес")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert [c.name for c in calls] == ["report"]
    cmd_obj = calls[0].args[1]
    assert cmd_obj.args == "12"


@pytest.mark.asyncio
async def test_month_alone_routes_to_period(
    calls: list[_CallRecord],
) -> None:
    msg = _FakeMessage("май")
    await nl_router.nl_dispatch(msg, db_user=_user())  # type: ignore[arg-type]
    assert [c.name for c in calls] == ["period"]
