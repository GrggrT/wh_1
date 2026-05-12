"""Tests for the FSM-transition Sentry breadcrumb middleware."""
# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any

import pytest
from src.bot.middlewares.fsm_breadcrumbs import FSMBreadcrumbMiddleware


class _FakeState:
    def __init__(self, before: str | None, after: str | None) -> None:
        self._before = before
        self._after = after
        self._calls = 0

    async def get_state(self) -> str | None:
        self._calls += 1
        return self._before if self._calls == 1 else self._after


class _FakeMessage:
    pass


@pytest.mark.asyncio
async def test_middleware_records_breadcrumb_on_state_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crumbs: list[dict[str, Any]] = []
    import src.bot.middlewares.fsm_breadcrumbs as mod

    def _capture(**kw: Any) -> None:
        crumbs.append(kw)

    monkeypatch.setattr(mod.sentry_sdk, "add_breadcrumb", _capture)
    # Monkey-patch isinstance check by swapping Message in the module.
    monkeypatch.setattr(mod, "Message", _FakeMessage)

    state = _FakeState(before=None, after="Onboarding:awaiting_name")

    async def handler(_event: Any, _data: dict[str, Any]) -> str:
        return "ok"

    mw = FSMBreadcrumbMiddleware()
    out = await mw(handler, _FakeMessage(), {"state": state})

    assert out == "ok"
    assert len(crumbs) == 1
    assert crumbs[0]["category"] == "fsm"
    assert "Onboarding:awaiting_name" in crumbs[0]["message"]


@pytest.mark.asyncio
async def test_middleware_skips_breadcrumb_when_state_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crumbs: list[dict[str, Any]] = []
    import src.bot.middlewares.fsm_breadcrumbs as mod

    monkeypatch.setattr(
        mod.sentry_sdk, "add_breadcrumb",
        lambda **kw: crumbs.append(kw),
    )
    monkeypatch.setattr(mod, "Message", _FakeMessage)

    state = _FakeState(before="X:y", after="X:y")

    async def handler(_event: Any, _data: dict[str, Any]) -> str:
        return "ok"

    mw = FSMBreadcrumbMiddleware()
    await mw(handler, _FakeMessage(), {"state": state})

    assert crumbs == []


@pytest.mark.asyncio
async def test_middleware_passes_through_unknown_event_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crumbs: list[dict[str, Any]] = []
    import src.bot.middlewares.fsm_breadcrumbs as mod

    monkeypatch.setattr(
        mod.sentry_sdk, "add_breadcrumb",
        lambda **kw: crumbs.append(kw),
    )

    async def handler(_event: Any, _data: dict[str, Any]) -> str:
        return "ok"

    mw = FSMBreadcrumbMiddleware()
    out = await mw(handler, object(), {})
    assert out == "ok"
    assert crumbs == []


@pytest.mark.asyncio
async def test_middleware_records_breadcrumb_even_when_handler_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crumbs: list[dict[str, Any]] = []
    import src.bot.middlewares.fsm_breadcrumbs as mod

    monkeypatch.setattr(
        mod.sentry_sdk, "add_breadcrumb",
        lambda **kw: crumbs.append(kw),
    )
    monkeypatch.setattr(mod, "Message", _FakeMessage)

    state = _FakeState(before=None, after="X:y")

    async def handler(_event: Any, _data: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    mw = FSMBreadcrumbMiddleware()
    with pytest.raises(RuntimeError):
        await mw(handler, _FakeMessage(), {"state": state})

    # Breadcrumb still recorded so Sentry has the trail.
    assert len(crumbs) == 1
