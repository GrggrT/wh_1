"""Optional Sentry error tracking.

Initialises the Sentry SDK when ``settings.sentry_dsn`` is non-empty;
otherwise this is a no-op. The aiogram error handler in ``src/bot/main.py``
captures exceptions explicitly so all handler errors reach Sentry even
when bubbling-up logging would not.
"""

from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from src.core.config import Settings


def init_sentry(settings: Settings) -> bool:
    """Initialise Sentry. Returns True when enabled, False when DSN empty."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    return True


def capture_exception(exc: BaseException) -> None:
    """Send an exception to Sentry. Safe to call when Sentry is disabled."""
    sentry_sdk.capture_exception(exc)
