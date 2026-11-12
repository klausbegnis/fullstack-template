"""DB-backed tests for `RateLimitWindowRepository`'s upsert and expiry purge.

Each test runs in a transaction that is rolled back, under a unique scope.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.rate_limit_window import RateLimitWindow
from app.repositories.rate_limit_windows import RateLimitWindowRepository, WindowCount

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=15)
DIGEST = hashlib.sha256(b"member@example.test").digest()


@asynccontextmanager
async def rolled_back_session() -> AsyncIterator[AsyncSession]:
    """Yield a session whose writes are always rolled back, never committed."""
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            async with AsyncSession(bind=connection) as session:
                try:
                    yield session
                finally:
                    await outer.rollback()
    finally:
        await engine.dispose()


def _scope() -> str:
    return f"test-{uuid.uuid4().hex}"


def test_the_first_hit_opens_a_window_and_the_next_counts_in_it() -> None:
    async def scenario() -> tuple[WindowCount, WindowCount]:
        async with rolled_back_session() as session:
            windows = RateLimitWindowRepository(session)
            scope = _scope()
            first = await windows.hit(scope, DIGEST, now=NOW, window=WINDOW)
            second = await windows.hit(
                scope, DIGEST, now=NOW + timedelta(minutes=5), window=WINDOW
            )
            return first, second

    first, second = asyncio.run(scenario())

    assert first == WindowCount(hits=1, resets_at=NOW + WINDOW)
    assert second == WindowCount(hits=2, resets_at=NOW + WINDOW)


def test_a_hit_after_the_window_ended_restarts_it_at_one() -> None:
    later = NOW + WINDOW + timedelta(seconds=1)

    async def scenario() -> tuple[WindowCount, int]:
        async with rolled_back_session() as session:
            windows = RateLimitWindowRepository(session)
            scope = _scope()
            for _ in range(3):
                await windows.hit(scope, DIGEST, now=NOW, window=WINDOW)
            restarted = await windows.hit(scope, DIGEST, now=later, window=WINDOW)
            rows = await session.scalar(
                select(RateLimitWindow.hits).where(RateLimitWindow.scope == scope)
            )
            return restarted, rows or 0

    restarted, stored_hits = asyncio.run(scenario())

    assert restarted == WindowCount(hits=1, resets_at=later + WINDOW)
    assert stored_hits == 1


def test_delete_expired_removes_only_ended_windows_up_to_the_limit() -> None:
    async def scenario() -> tuple[int, int, list[datetime]]:
        async with rolled_back_session() as session:
            windows = RateLimitWindowRepository(session)
            scope = _scope()
            for index, opened in enumerate(
                (NOW - timedelta(hours=3), NOW - timedelta(hours=2), NOW)
            ):
                await windows.hit(scope, bytes([index]) * 32, now=opened, window=WINDOW)
            counted = await windows.count_expired(before=NOW, limit=500)
            deleted = await windows.delete_expired(before=NOW, limit=1)
            remaining = await session.scalars(
                select(RateLimitWindow.resets_at)
                .where(RateLimitWindow.scope == scope)
                .order_by(RateLimitWindow.resets_at)
            )
            return counted, deleted, list(remaining.all())

    counted, deleted, remaining = asyncio.run(scenario())

    assert counted == 2
    assert deleted == 1
    assert remaining == [NOW - timedelta(hours=2) + WINDOW, NOW + WINDOW]
