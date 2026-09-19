from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, settings


def create_engine(
    database_url: str | None = None,
    *,
    db_settings: Settings | None = None,
) -> AsyncEngine:
    """Create the application's SQLAlchemy async engine."""
    config = db_settings or settings
    url = database_url or config.DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required to start the application; configure a "
            "PostgreSQL postgresql+asyncpg:// URL."
        )
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            "DATABASE_URL must use the postgresql+asyncpg:// SQLAlchemy URL scheme."
        )
    if config.DB_POOL_MIN_SIZE < 0 or config.DB_POOL_MAX_SIZE < 1:
        raise ValueError("DB_POOL_MIN_SIZE and DB_POOL_MAX_SIZE must be positive.")
    if config.DB_POOL_MIN_SIZE > config.DB_POOL_MAX_SIZE:
        raise ValueError("DB_POOL_MIN_SIZE cannot exceed DB_POOL_MAX_SIZE.")
    return create_async_engine(
        url,
        pool_size=config.DB_POOL_MAX_SIZE,
        max_overflow=0,
        pool_timeout=config.DB_POOL_TIMEOUT,
        pool_recycle=config.DB_POOL_RECYCLE,
        pool_pre_ping=config.DB_POOL_PRE_PING,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Build a factory that creates one independent session per request."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def verify_connection(engine: AsyncEngine) -> None:
    """Fail startup early when PostgreSQL is unavailable."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one session per request and rollback failed requests."""
    factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "db_session_factory", None
    )
    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    async with factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


async def dispose_engine(engine: AsyncEngine | None) -> None:
    """Dispose all pooled connections owned by the application."""
    if engine is not None:
        await engine.dispose()
