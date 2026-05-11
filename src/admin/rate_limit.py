"""In-memory failed-auth tracker for the admin panel.

Single-tenant deployment, single uvicorn worker — so an in-memory store
is adequate. Records the timestamp of each failed authentication per
client IP, prunes entries that are older than ``window_seconds``, and
treats the client as blocked when the number of recent failures meets
or exceeds ``max_failures``. The block clears automatically
``block_seconds`` after the most recent recorded failure.

Successful authentication clears the IP from the tracker via
``clear_failures``.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class _Tracker:
    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _prune(self, ip: str, now: float, window_seconds: int) -> list[float]:
        cutoff = now - window_seconds
        recent = [ts for ts in self._failures[ip] if ts >= cutoff]
        self._failures[ip] = recent
        return recent

    def is_blocked(
        self,
        ip: str,
        *,
        max_failures: int,
        window_seconds: int,
        block_seconds: int,
        now: float | None = None,
    ) -> bool:
        ts_now = time.monotonic() if now is None else now
        with self._lock:
            recent = self._prune(ip, ts_now, window_seconds)
            if len(recent) < max_failures:
                return False
            most_recent = recent[-1]
            return ts_now - most_recent < block_seconds

    def record_failure(
        self,
        ip: str,
        *,
        window_seconds: int,
        now: float | None = None,
    ) -> None:
        ts_now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(ip, ts_now, window_seconds)
            self._failures[ip].append(ts_now)

    def clear_failures(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)

    def reset(self) -> None:
        """Test hook: drop all state."""
        with self._lock:
            self._failures.clear()


tracker = _Tracker()
