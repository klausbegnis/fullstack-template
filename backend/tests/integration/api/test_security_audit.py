"""Prove each account security event leaves an `iam.security_events` row via the API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
import json
import logging
import os
import uuid

from fastapi.testclient import TestClient
from httpx import Response
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings, settings
from app.core.database import create_session_factory, get_session
from app.core.security import hash_password
from app.main import app
from app.models.security_event import SecurityEvent
from app.models.user import User, UserRole
from tests.support.browser import BROWSER_HEADERS

PASSWORD = "Correct horse battery staple 123!"
WRONG_PASSWORD = "Not the right password 789!"
NEW_MEMBER_PASSWORD = "A brand new member password 456!"


@dataclass
class _Account:
    id: uuid.UUID
    email: str


@dataclass
class _Harness:
    engine: AsyncEngine
    client: TestClient
    admin: _Account
    member: _Account

    def login(self, account: _Account, password: str = PASSWORD) -> Response:
        return self.client.post(
            "/auth/login", json={"email": account.email, "password": password}
        )

    def events(self, user_id: uuid.UUID) -> list[SecurityEvent]:
        async def load() -> list[SecurityEvent]:
            async with create_session_factory(self.engine)() as session:
                rows = await session.scalars(
                    select(SecurityEvent)
                    .where(SecurityEvent.user_id == user_id)
                    .order_by(SecurityEvent.created_at)
                )
                return list(rows.all())

        return asyncio.run(load())

    def actions(self, user_id: uuid.UUID) -> list[str]:
        return [event.action for event in self.events(user_id)]


def _new_user(role: UserRole) -> User:
    email = f"security-{role.value}-{uuid.uuid4()}@example.test"
    return User(
        name="Audit Test",
        email=email,
        email_normalized=email,
        password_hash=hash_password(PASSWORD),
        role=role,
    )


@pytest.fixture
def harness() -> Iterator[_Harness]:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    factory = create_session_factory(engine)
    admin, member = _new_user(UserRole.ADMIN), _new_user(UserRole.MEMBER)

    async def seed() -> None:
        async with factory() as session:
            session.add_all([admin, member])
            await session.commit()

    asyncio.run(seed())

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        TESTING=True,
        AUTH_COOKIE_SECURE=False,
    )
    with TestClient(app, headers=BROWSER_HEADERS) as client:
        yield _Harness(
            engine=engine,
            client=client,
            admin=_Account(admin.id, admin.email),
            member=_Account(member.id, member.email),
        )
    app.dependency_overrides.clear()

    async def cleanup() -> None:
        async with factory() as session:
            await session.execute(
                delete(SecurityEvent).where(
                    SecurityEvent.actor_user_id.in_([admin.id, member.id])
                    | SecurityEvent.user_id.in_([admin.id, member.id])
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(cleanup())


def _logged(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )


def _assert_no_secrets(
    harness: _Harness, caplog: pytest.LogCaptureFixture, *secrets: str
) -> None:
    events = harness.events(harness.member.id) + harness.events(harness.admin.id)
    for event in events:
        payload = json.dumps(event.payload)
        assert "@" not in payload
        for secret in secrets:
            assert secret not in payload
    logged = _logged(caplog)
    assert "security event recorded" in logged
    for value in (harness.member.email, harness.admin.email, *secrets):
        assert value not in logged


def test_login_success_records_one_event_for_the_user(
    harness: _Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    assert harness.login(harness.member).status_code == 200

    [event] = harness.events(harness.member.id)
    assert event.action == "auth.login_succeeded"
    assert event.actor_user_id == harness.member.id
    _assert_no_secrets(harness, caplog, PASSWORD)


def test_wrong_password_returns_401_and_commits_a_failure_row(
    harness: _Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    response = harness.login(harness.member, WRONG_PASSWORD)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    [event] = harness.events(harness.member.id)
    assert event.action == "auth.login_failed"
    assert event.payload == {"reason": "invalid_password"}
    _assert_no_secrets(harness, caplog, WRONG_PASSWORD, PASSWORD)


def test_unknown_email_returns_401_and_writes_no_row(
    harness: _Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    unknown = f"nobody-{uuid.uuid4()}@example.test"

    response = harness.client.post(
        "/auth/login", json={"email": unknown, "password": PASSWORD}
    )

    assert response.status_code == 401
    assert harness.events(harness.member.id) + harness.events(harness.admin.id) == []
    logged = _logged(caplog)
    assert "login failed for an unknown account" in logged
    assert unknown not in logged
    assert PASSWORD not in logged


def test_logout_records_one_event_for_the_session_user(
    harness: _Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    assert harness.login(harness.member).status_code == 200
    csrf = harness.client.cookies[settings.AUTH_CSRF_COOKIE]

    logout = harness.client.post("/auth/logout", headers={"X-CSRF-Token": csrf})

    assert logout.status_code == 204
    assert harness.actions(harness.member.id) == [
        "auth.login_succeeded",
        "auth.logout",
    ]
    assert harness.events(harness.member.id)[-1].actor_user_id == harness.member.id
    _assert_no_secrets(harness, caplog, PASSWORD)


def test_refresh_token_replay_records_reuse(harness: _Harness) -> None:
    login = harness.login(harness.member)
    cookies = {
        settings.AUTH_REFRESH_COOKIE: login.cookies[settings.AUTH_REFRESH_COOKIE],
        settings.AUTH_CSRF_COOKIE: login.cookies[settings.AUTH_CSRF_COOKIE],
    }
    csrf = {"X-CSRF-Token": cookies[settings.AUTH_CSRF_COOKIE]}
    harness.client.cookies.clear()
    rotated = harness.client.post("/auth/refresh", cookies=cookies, headers=csrf)
    assert rotated.status_code == 204

    harness.client.cookies.clear()
    replayed = harness.client.post("/auth/refresh", cookies=cookies, headers=csrf)

    assert replayed.status_code == 401
    reuse = [
        event
        for event in harness.events(harness.member.id)
        if event.action == "auth.refresh_token_reused"
    ]
    assert len(reuse) == 1
    assert reuse[0].actor_user_id is None


def test_admin_user_management_records_the_admin_as_actor(
    harness: _Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    assert harness.login(harness.admin).status_code == 200
    csrf = {"X-CSRF-Token": harness.client.cookies[settings.AUTH_CSRF_COOKIE]}
    target = f"/users/{harness.member.id}"

    created = harness.client.post(
        "/users",
        json={
            "name": "Created Member",
            "email": f"created-{uuid.uuid4()}@example.test",
            "password": NEW_MEMBER_PASSWORD,
        },
        headers=csrf,
    )
    renamed = harness.client.patch(target, json={"name": "Another Name"}, headers=csrf)
    promoted = harness.client.patch(target, json={"role": "admin"}, headers=csrf)
    disabled = harness.client.delete(target, headers=csrf)

    assert created.status_code == 201
    assert renamed.status_code == 200
    assert promoted.status_code == 200
    assert disabled.status_code == 204
    created_id = uuid.UUID(created.json()["data"]["id"])
    [created_event] = harness.events(created_id)
    assert created_event.action == "user.created"
    assert created_event.actor_user_id == harness.admin.id
    assert created_event.payload == {"role": "member"}
    updated, role_changed, disabled_event = harness.events(harness.member.id)
    assert updated.action == "user.updated"
    assert updated.payload == {"fields": ["name"]}
    assert role_changed.action == "user.role_changed"
    assert role_changed.payload == {"old_role": "member", "role": "admin"}
    assert disabled_event.action == "user.disabled"
    assert {
        event.actor_user_id for event in (updated, role_changed, disabled_event)
    } == {harness.admin.id}
    _assert_no_secrets(harness, caplog, PASSWORD, NEW_MEMBER_PASSWORD)
