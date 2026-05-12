"""Phase 7.6: tiny DB-query counter for performance regression tracking.

Wraps a block of async work and counts how many SQL statements the
default engine executes during it via SQLAlchemy's ``before_cursor_execute``
event. Single-tenant bot, so concurrent unrelated queries leaking into the
count is a theoretical concern only; in practice the scheduler runs serially
and handlers are awaited end-to-end.

Usage::

    with count_queries() as q:
        async for session in get_session():
            await do_work(session)
    logger.info("report_query_count", queries=q.count)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import event

from src.core import db as _db


@dataclass
class QueryCounter:
    count: int = 0


@contextmanager
def count_queries() -> Iterator[QueryCounter]:
    counter = QueryCounter()
    if _db.engine is None:
        yield counter
        return
    sync_eng = _db.engine.sync_engine

    def _on_exec(*_args: object, **_kwargs: object) -> None:
        counter.count += 1

    event.listen(sync_eng, "before_cursor_execute", _on_exec)
    try:
        yield counter
    finally:
        event.remove(sync_eng, "before_cursor_execute", _on_exec)
