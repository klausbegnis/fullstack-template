import asyncio
import os

import pytest
from sqlalchemy import text

from app.config import Settings
from app.core.database import create_engine, create_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="PostgreSQL DATABASE_URL is not configured",
    ),
]


def test_sessions_are_isolated_and_recover_after_rollback() -> None:
    asyncio.run(_exercise_sessions())


async def _exercise_sessions() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Settings(DATABASE_URL=database_url, TESTING=True)
    engine = create_engine(db_settings=config)
    factory = create_session_factory(engine)
    try:
        async with factory() as first, factory() as second:
            assert first is not second
            assert (await first.scalar(text("SELECT 1"))) == 1
            assert (await second.scalar(text("SELECT 1"))) == 1

        with pytest.raises(RuntimeError):
            async with factory() as failed:
                await failed.execute(text("SELECT 1"))
                raise RuntimeError("simulated service failure")

        async with factory() as next_session:
            assert (await next_session.scalar(text("SELECT 1"))) == 1
    finally:
        await engine.dispose()
