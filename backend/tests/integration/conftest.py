"""Apply the integration tier's marker and database precondition in one place.

Repeating `pytestmark` per module drifts: a file that forgets the skip fails the
whole run on a machine without PostgreSQL. The tier owns both decisions.

Rate-limit windows persist in the database, and every `TestClient` request
comes from the same client address, so each test starts with no window: one
test's logins never throttle the next test's. Hits go through the real
counter, on a `NullPool` engine of this process, because a client used outside
its `with` block runs each request on a fresh event loop that the lifespan
engine's pooled connections do not belong to.
"""

import asyncio
from collections.abc import Callable
import os
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import SessionFactory, create_session_factory
from app.dependencies import ClockDep, get_rate_limit_counter
from app.dependencies.rate_limit import RateLimitCounter, SharedWindowCounter
from app.main import app
from app.models.rate_limit_window import RateLimitWindow

TIER_ROOT = Path(__file__).parent
REQUIRES_DATABASE = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="PostgreSQL DATABASE_URL is not configured",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test under `tests/integration` and skip it without a database."""
    for item in items:
        if TIER_ROOT in Path(item.path).parents:
            item.add_marker(pytest.mark.integration)
            item.add_marker(REQUIRES_DATABASE)


_counter_engines: dict[str, AsyncEngine] = {}


def _counter_engine(database_url: str) -> AsyncEngine:
    if database_url not in _counter_engines:
        _counter_engines[database_url] = create_async_engine(
            database_url, poolclass=NullPool
        )
    return _counter_engines[database_url]


async def _delete_rate_limit_windows(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(delete(RateLimitWindow))


def _counter_on(factory: SessionFactory) -> Callable[..., RateLimitCounter]:
    def counter(clock: ClockDep) -> RateLimitCounter:
        return SharedWindowCounter(lambda: factory, clock)

    return counter


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Empty the rate-limit windows and count on a `NullPool` engine, per test.

    A hook rather than a fixture, so it also precedes module-scoped fixtures
    that log in, and survives a previous test clearing the overrides.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url or TIER_ROOT not in Path(item.path).parents:
        return
    engine = _counter_engine(database_url)
    asyncio.run(_delete_rate_limit_windows(engine))
    app.dependency_overrides[get_rate_limit_counter] = _counter_on(
        create_session_factory(engine)
    )


def pytest_unconfigure() -> None:
    """Dispose the counter engines this process opened."""
    for engine in _counter_engines.values():
        asyncio.run(engine.dispose())
