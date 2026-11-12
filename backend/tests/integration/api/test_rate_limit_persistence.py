"""Login throttling holds across app instances, restarts and an injected clock.

Each `with TestClient(app)` block is one app instance: its lifespan builds its
own engine and session factory on the shared database and disposes them on
exit, so a second block is a restarted instance. The fixture drops the tier's
counter override, so hits go through the production `get_rate_limit_counter`
and each instance's own session factory into `iam.rate_limit_windows`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
import os
import uuid

from fastapi.testclient import TestClient
from httpx import Response
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings, settings
from app.core.database import create_session_factory
from app.core.rate_limit import UNKNOWN_CLIENT
from app.core.security import hash_password
from app.dependencies import get_clock, get_rate_limit_counter
from app.main import app
from app.models.rate_limit_window import RateLimitWindow
from app.models.user import UserRole
from app.repositories.users import UserRepository
from app.services.rate_limits import digest_key, subject_digest
from tests.support.browser import BROWSER_HEADERS

KEY = digest_key(settings.AUTH_JWT_SECRET.get_secret_value())

PASSWORD = "Correct horse battery staple 123!"
TEST_CLIENT_IP = UNKNOWN_CLIENT
LOGIN_WINDOW = timedelta(seconds=900)


def _settings(**overrides: object) -> Settings:
    return Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        TESTING=True,
        DEBUG=True,
        ENVIRONMENT="development",
        AUTH_COOKIE_SECURE=False,
        **overrides,  # type: ignore[arg-type]
    )


async def _seed_user(email: str) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with create_session_factory(engine)() as session:
            await UserRepository(session).create_bootstrap_user(
                email=email, password_hash=hash_password(PASSWORD), role=UserRole.MEMBER
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _load_windows() -> list[RateLimitWindow]:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with create_session_factory(engine)() as session:
            rows = await session.scalars(
                select(RateLimitWindow).order_by(RateLimitWindow.scope)
            )
            return list(rows.all())
    finally:
        await engine.dispose()


def _windows() -> dict[str, RateLimitWindow]:
    return {row.scope: row for row in asyncio.run(_load_windows())}


@pytest.fixture
def email() -> Iterator[str]:
    """Seed a member, count through the production counter; reset overrides after."""
    address = f"persist-{uuid.uuid4()}@example.test"
    asyncio.run(_seed_user(address))
    app.dependency_overrides.pop(get_rate_limit_counter, None)
    app.dependency_overrides[get_settings] = lambda: _settings()
    yield address
    app.dependency_overrides.clear()


def _wrong_password_logins(email: str, attempts: int) -> list[Response]:
    with TestClient(app, headers=BROWSER_HEADERS) as instance:
        return [
            instance.post(
                "/auth/login", json={"email": email, "password": "definitely wrong"}
            )
            for _ in range(attempts)
        ]


def test_the_eleventh_login_through_two_instances_is_throttled(email: str) -> None:
    first_instance = _wrong_password_logins(email, 5)
    second_instance = _wrong_password_logins(email, 6)

    statuses = [response.status_code for response in first_instance + second_instance]
    throttled = second_instance[-1]
    assert statuses == [401] * 10 + [429]
    assert int(throttled.headers["Retry-After"]) >= 1
    assert throttled.json()["error"]["code"] == "rate_limited"


def test_a_restarted_instance_sees_the_earlier_wrong_password_hits(email: str) -> None:
    _wrong_password_logins(email, 10)

    after_restart = _wrong_password_logins(email, 1)[0]

    assert _windows()["login:subject"].hits == 11
    assert after_restart.status_code == 429


def test_the_next_attempt_after_the_window_restarts_the_count(email: str) -> None:
    opened = datetime.now(UTC)
    clock = {"now": opened}
    app.dependency_overrides[get_clock] = lambda: lambda: clock["now"]
    blocked = _wrong_password_logins(email, 11)[-1]
    clock["now"] = opened + LOGIN_WINDOW + timedelta(seconds=1)

    allowed = _wrong_password_logins(email, 1)[0]

    window = _windows()["login:subject"]
    assert blocked.status_code == 429
    assert allowed.status_code == 401
    assert window.hits == 1
    assert window.resets_at == clock["now"] + LOGIN_WINDOW


def test_windows_store_only_digests_never_the_email_or_ip(email: str) -> None:
    _wrong_password_logins(email, 1)

    windows = _windows()

    assert sorted(windows) == ["login:ip", "login:subject"]
    assert windows["login:subject"].subject_digest == subject_digest(email, KEY)
    assert windows["login:ip"].subject_digest == subject_digest(TEST_CLIENT_IP, KEY)
    for row in windows.values():
        stored = repr(
            (row.scope, row.subject_digest, row.resets_at, row.hits)
        ).encode() + bytes(row.subject_digest)
        assert len(row.subject_digest) == 32
        assert email.encode() not in stored
        assert TEST_CLIENT_IP.encode() not in stored


def test_a_disabled_limiter_never_throttles_and_writes_no_window(email: str) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(RATE_LIMIT_ENABLED=False)

    statuses = [response.status_code for response in _wrong_password_logins(email, 12)]

    assert statuses == [401] * 12
    assert _windows() == {}


def test_a_login_without_an_email_still_counts_by_ip(email: str) -> None:
    with TestClient(app, headers=BROWSER_HEADERS) as instance:
        response = instance.post("/auth/login", json={"password": PASSWORD})

    assert response.status_code == 422
    assert sorted(_windows()) == ["login:ip"]
