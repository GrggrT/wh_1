"""Phase 7.x: Sentry breadcrumbs for FSM state transitions.

Records a breadcrumb every time a handler changes the FSM state of the
user it's running for. The before/after state names are captured so any
later crash in the same request has the FSM trail visible in Sentry.

No-op when Sentry isn't configured (``sentry_sdk.add_breadcrumb`` is
always safe to call: it stores into the SDK's in-memory hub regardless
of whether init has been called).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import sentry_sdk
from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject


async def _get_state(state: FSMContext | None) -> str | None:
    if state is None:
        return None
    return await state.get_state()


class FSMBreadcrumbMiddleware(BaseMiddleware):
    """Drop a Sentry breadcrumb when a handler changes the FSM state."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        if not isinstance(event, Message | CallbackQuery):
            return await handler(event, data)
        state: FSMContext | None = data.get("state")
        before = await _get_state(state)
        try:
            return await handler(event, data)
        finally:
            after = await _get_state(state)
            if before != after:
                sentry_sdk.add_breadcrumb(
                    category="fsm",
                    level="info",
                    message=f"{before} -> {after}",
                    data={
                        "event": type(event).__name__,
                    },
                )
