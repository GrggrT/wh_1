from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import Settings

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    global engine, session_factory  # noqa: PLW0603
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert session_factory is not None, "Engine not initialized"
    async with session_factory() as session:
        yield session


async def dispose_engine() -> None:
    global engine, session_factory  # noqa: PLW0603
    if engine is not None:
        await engine.dispose()
        engine = None
        session_factory = None
