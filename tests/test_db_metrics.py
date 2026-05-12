"""Phase 7.6: db_metrics.count_queries tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from src.core import db as db_module
from src.core.db_metrics import count_queries


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    original_engine = db_module.engine
    original_factory = db_module.session_factory
    db_module.engine = eng
    db_module.session_factory = async_sessionmaker(eng, expire_on_commit=False)
    try:
        yield eng
    finally:
        db_module.engine = original_engine
        db_module.session_factory = original_factory
        await eng.dispose()


@pytest.mark.asyncio
async def test_count_queries_counts_each_execution(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with count_queries() as q:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("SELECT 2"))
            await conn.execute(text("SELECT 3"))
    assert q.count == 3


@pytest.mark.asyncio
async def test_count_queries_isolates_after_exit(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with count_queries() as q1:
            await conn.execute(text("SELECT 1"))
        # Run more queries after exiting the context.
        await conn.execute(text("SELECT 2"))
        await conn.execute(text("SELECT 3"))
    assert q1.count == 1


def test_count_queries_no_engine_yields_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_module, "engine", None)
    with count_queries() as q:
        pass
    assert q.count == 0
