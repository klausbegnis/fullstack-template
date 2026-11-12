import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import os
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.rate_limit_window import RateLimitWindow


@asynccontextmanager
async def rolled_back_session() -> AsyncIterator[AsyncSession]:
    """Yield a session whose writes are always rolled back, never committed."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
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


async def _hit(session: AsyncSession, scope: str, subject_digest: bytes) -> int:
    statement = (
        insert(RateLimitWindow)
        .values(
            id=uuid.uuid4(),
            scope=scope,
            subject_digest=subject_digest,
            resets_at=datetime.now(UTC) + timedelta(minutes=15),
            hits=1,
        )
        .on_conflict_do_update(
            index_elements=["scope", "subject_digest"],
            set_={"hits": RateLimitWindow.hits + 1},
        )
        .returning(RateLimitWindow.hits)
    )
    return (await session.execute(statement)).scalar_one()


def test_upserting_the_same_window_twice_counts_two_hits() -> None:
    async def scenario() -> tuple[int, int]:
        async with rolled_back_session() as session:
            scope = f"login-{uuid.uuid4().hex}"
            subject_digest = hashlib.sha256(b"member@example.test").digest()
            first = await _hit(session, scope, subject_digest)
            second = await _hit(session, scope, subject_digest)
            return first, second

    first_hits, second_hits = asyncio.run(scenario())

    assert first_hits == 1
    assert second_hits == 2
