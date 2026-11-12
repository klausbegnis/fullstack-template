"""DB-backed tests for the `purge_rate_limit_windows` command.

The tier's conftest empties `iam.rate_limit_windows` before each test, so the
counts the command reports are this test's rows only.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.commands.purge_rate_limit_windows import run
from app.core.database import create_session_factory
from app.models.rate_limit_window import RateLimitWindow

BACKEND_ROOT = Path(__file__).resolve().parents[3]


async def _insert(resets_at: list[datetime]) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with create_session_factory(engine)() as session:
            session.add_all(
                RateLimitWindow(
                    scope="login:ip",
                    subject_digest=uuid.uuid4().bytes * 2,
                    resets_at=moment,
                    hits=1,
                )
                for moment in resets_at
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _remaining() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with create_session_factory(engine)() as session:
            return (
                await session.scalar(select(func.count()).select_from(RateLimitWindow))
            ) or 0
    finally:
        await engine.dispose()


def _seed_two_ended_and_one_live() -> None:
    now = datetime.now(UTC)
    asyncio.run(
        _insert(
            [
                now - timedelta(hours=2),
                now - timedelta(hours=1),
                now + timedelta(hours=1),
            ]
        )
    )


def test_run_deletes_only_windows_whose_reset_has_passed() -> None:
    _seed_two_ended_and_one_live()

    deleted = asyncio.run(run())

    assert deleted == 2
    assert asyncio.run(_remaining()) == 1


def test_run_respects_the_limit() -> None:
    _seed_two_ended_and_one_live()

    deleted = asyncio.run(run(limit=1))

    assert deleted == 1
    assert asyncio.run(_remaining()) == 2


def test_dry_run_counts_and_deletes_nothing() -> None:
    _seed_two_ended_and_one_live()

    counted = asyncio.run(run(dry_run=True))

    assert counted == 2
    assert asyncio.run(_remaining()) == 3


def test_command_prints_the_count_it_deleted() -> None:
    _seed_two_ended_and_one_live()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.commands.purge_rate_limit_windows",
            "--limit",
            "10",
        ],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "2"
    assert asyncio.run(_remaining()) == 1
