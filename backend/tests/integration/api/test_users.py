from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import os
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings
from app.core.database import create_session_factory, get_session
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole
from app.repositories.users import UserRepository


@pytest.fixture
def users_client() -> TestClient:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    factory = create_session_factory(engine)
    admin_email = f"admin-{uuid.uuid4()}@example.test"
    admin_password = "Correct horse battery staple 123!"

    async def seed() -> None:
        async with factory() as session:
            await UserRepository(session).create_bootstrap_user(
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=UserRole.ADMIN,
            )
            await session.commit()

    asyncio.run(seed())

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        TESTING=True,
        DEBUG=True,
        AUTH_COOKIE_SECURE=False,
    )
    with TestClient(app) as client:
        app.state.db_session_factory = factory
        client.admin_email = admin_email  # type: ignore[attr-defined]
        client.admin_password = admin_password  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )


def _create_user(
    client: TestClient,
    *,
    email: str,
    password: str = "Correct horse battery staple!",
    role: str = "member",
    name: str = "Test User",
):
    return client.post(
        "/users",
        json={"name": name, "email": email, "password": password, "role": role},
    )


def _disable_other_active_admins(keep: uuid.UUID) -> None:
    async def run() -> None:
        factory = app.state.db_session_factory
        async with factory() as session:
            await session.execute(
                update(User)
                .where(User.role == UserRole.ADMIN, User.id != keep)
                .values(disabled_at=datetime.now(UTC))
            )
            await session.commit()

    asyncio.run(run())


def test_unauthenticated_request_is_rejected(users_client: TestClient) -> None:
    response = users_client.get("/users")
    assert response.status_code == 401


def test_admin_can_create_get_update_and_disable_a_user(
    users_client: TestClient,
) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    email = f"member-{uuid.uuid4()}@example.test"

    created = _create_user(users_client, email=email)
    assert created.status_code == 201
    user_id = created.json()["data"]["id"]

    fetched = users_client.get(f"/users/{user_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["email"] == email

    updated = users_client.patch(f"/users/{user_id}", json={"name": "Renamed Member"})
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Renamed Member"

    disabled = users_client.delete(f"/users/{user_id}")
    assert disabled.status_code == 204

    after_disable = users_client.get(f"/users/{user_id}")
    assert after_disable.json()["data"]["disabled_at"] is not None


def test_admin_can_list_users_with_pagination(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    for _ in range(3):
        assert (
            _create_user(
                users_client, email=f"list-{uuid.uuid4()}@example.test"
            ).status_code
            == 201
        )

    first_page = users_client.get("/users", params={"page": 1, "page_size": 2})
    assert first_page.status_code == 200
    body = first_page.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["data"]) == 2
    assert body["total"] >= 4
    assert body["total_pages"] >= 2


def test_non_admin_cannot_list_or_create_users(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    member_email = f"member-{uuid.uuid4()}@example.test"
    member_password = "Correct horse battery staple!"
    created = _create_user(users_client, email=member_email, password=member_password)
    assert created.status_code == 201

    member_client = TestClient(app)
    _login(member_client, member_email, member_password)

    assert member_client.get("/users").status_code == 403
    assert (
        _create_user(
            member_client, email=f"nope-{uuid.uuid4()}@example.test"
        ).status_code
        == 403
    )


def test_non_admin_can_update_self_but_not_others(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    member_password = "Correct horse battery staple!"
    member_email = f"member-{uuid.uuid4()}@example.test"
    other_email = f"member-{uuid.uuid4()}@example.test"
    member_id = _create_user(
        users_client, email=member_email, password=member_password
    ).json()["data"]["id"]
    other_id = _create_user(
        users_client, email=other_email, password=member_password
    ).json()["data"]["id"]

    member_client = TestClient(app)
    _login(member_client, member_email, member_password)

    self_update = member_client.patch(
        f"/users/{member_id}", json={"name": "Self Updated"}
    )
    assert self_update.status_code == 200

    other_update = member_client.patch(
        f"/users/{other_id}", json={"name": "Should Not Work"}
    )
    assert other_update.status_code == 403

    other_delete = member_client.delete(f"/users/{other_id}")
    assert other_delete.status_code == 403


def test_non_admin_cannot_escalate_own_role(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    member_password = "Correct horse battery staple!"
    member_email = f"member-{uuid.uuid4()}@example.test"
    member_id = _create_user(
        users_client, email=member_email, password=member_password
    ).json()["data"]["id"]

    member_client = TestClient(app)
    _login(member_client, member_email, member_password)

    escalation = member_client.patch(f"/users/{member_id}", json={"role": "admin"})
    assert escalation.status_code == 403


def test_get_unknown_user_returns_404(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    response = users_client.get(f"/users/{uuid.uuid4()}")
    assert response.status_code == 404


def test_create_user_with_duplicate_email_returns_409(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    email = f"dup-{uuid.uuid4()}@example.test"
    assert _create_user(users_client, email=email).status_code == 201
    duplicate = _create_user(users_client, email=email)
    assert duplicate.status_code == 409


def test_last_admin_guard_blocks_demotion_and_disable(users_client: TestClient) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    admin_id = uuid.UUID(users_client.get("/auth/me").json()["id"])
    _disable_other_active_admins(keep=admin_id)

    demote = users_client.patch(f"/users/{admin_id}", json={"role": "member"})
    assert demote.status_code == 422

    disable = users_client.delete(f"/users/{admin_id}")
    assert disable.status_code == 422


def test_demoting_an_admin_succeeds_when_another_admin_remains(
    users_client: TestClient,
) -> None:
    _login(users_client, users_client.admin_email, users_client.admin_password)  # type: ignore[attr-defined]
    admin_id = uuid.UUID(users_client.get("/auth/me").json()["id"])
    _disable_other_active_admins(keep=admin_id)

    second_admin_email = f"admin2-{uuid.uuid4()}@example.test"
    second_admin_id = _create_user(
        users_client, email=second_admin_email, role="admin"
    ).json()["data"]["id"]

    demote = users_client.patch(f"/users/{second_admin_id}", json={"role": "member"})
    assert demote.status_code == 200
    assert demote.json()["data"]["role"] == "member"
