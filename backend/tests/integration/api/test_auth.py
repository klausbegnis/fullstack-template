from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import uuid

from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings, settings
from app.core.database import create_session_factory, get_session
from app.core.security import hash_password
from app.main import app
from app.models.auth_session import AuthSession
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from tests.support.browser import BROWSER_HEADERS


@pytest.fixture
def auth_client() -> TestClient:
    engine = create_async_engine(
        __import__("os").environ["DATABASE_URL"], poolclass=NullPool
    )
    factory = create_session_factory(engine)
    email = f"auth-{uuid.uuid4()}@example.test"
    password = "Correct horse battery staple 123!"

    async def seed() -> None:
        async with factory() as session:
            await UserRepository(session).create_bootstrap_user(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
            await session.commit()

    asyncio.run(seed())

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        DATABASE_URL=__import__("os").environ["DATABASE_URL"],
        TESTING=True,
        AUTH_COOKIE_SECURE=False,
    )
    with TestClient(app, headers=BROWSER_HEADERS) as client:
        app.state.db_session_factory = factory
        client.auth_email = email  # type: ignore[attr-defined]
        client.auth_password = password  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _login(client: TestClient):
    return client.post(
        "/auth/login",
        json={"email": client.auth_email, "password": client.auth_password},  # type: ignore[attr-defined]
        headers={"Origin": "http://localhost:3000"},
    )


def _csrf_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://localhost:3000",
        "X-CSRF-Token": client.cookies[settings.AUTH_CSRF_COOKIE],
    }


def _post_without_origin(client: TestClient, url: str, headers: dict[str, str]):
    request = client.build_request("POST", url, headers=headers)
    del request.headers["origin"]
    return client.send(request)


def _access_headers(value: str) -> dict[str, str]:
    return {"Cookie": f"{settings.AUTH_ACCESS_COOKIE}={value}"}


def test_invalid_credentials_are_indistinguishable(auth_client: TestClient) -> None:
    missing = auth_client.post(
        "/auth/login",
        json={"email": "nobody@example.test", "password": "wrong"},
    )
    wrong = auth_client.post(
        "/auth/login",
        json={"email": auth_client.auth_email, "password": "wrong"},  # type: ignore[attr-defined]
    )
    assert (missing.status_code, missing.json()["error"]) == (
        wrong.status_code,
        wrong.json()["error"],
    )
    assert missing.status_code == 401


def test_login_cookies_me_and_no_token_in_body(auth_client: TestClient) -> None:
    response = _login(auth_client)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == auth_client.auth_email  # type: ignore[attr-defined]
    assert "password" not in response.text
    assert "token" not in response.text.lower()
    assert {
        settings.AUTH_ACCESS_COOKIE,
        settings.AUTH_REFRESH_COOKIE,
        settings.AUTH_CSRF_COOKIE,
    } <= set(response.cookies)
    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]
    assert me.json()["role"] == "admin"


def test_openapi_does_not_expose_secrets_or_token_bodies(
    auth_client: TestClient,
) -> None:
    document = app.openapi()
    rendered = str(document)
    assert settings.AUTH_JWT_SECRET.get_secret_value() not in rendered
    assert "refresh_token" not in rendered
    assert "access_token" not in rendered


def test_invalid_jwt_and_inactive_session_return_401(auth_client: TestClient) -> None:
    login = _login(auth_client)
    access = login.cookies[settings.AUTH_ACCESS_COOKIE]
    claims = jwt.decode(
        access,
        settings.AUTH_JWT_SECRET.get_secret_value(),
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    sid = uuid.UUID(claims["sid"])
    auth_client.cookies.clear()
    tampered = access[:-1] + ("A" if access[-1] != "A" else "B")
    assert (
        auth_client.get("/auth/me", headers=_access_headers(tampered)).status_code
        == 401
    )
    expired = jwt.encode(
        {**claims, "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.AUTH_JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )
    assert (
        auth_client.get("/auth/me", headers=_access_headers(expired)).status_code == 401
    )
    wrong_issuer = jwt.encode(
        {**claims, "iss": "other"},
        settings.AUTH_JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )
    assert (
        auth_client.get("/auth/me", headers=_access_headers(wrong_issuer)).status_code
        == 401
    )

    async def expire() -> None:
        factory = app.state.db_session_factory
        async with factory() as session:
            await session.execute(
                update(AuthSession)
                .where(AuthSession.id == sid)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

    asyncio.run(expire())
    assert (
        auth_client.get("/auth/me", headers=_access_headers(access)).status_code == 401
    )


def test_csrf_origin_refresh_replay_and_logout(auth_client: TestClient) -> None:
    login = _login(auth_client)
    refresh = login.cookies[settings.AUTH_REFRESH_COOKIE]
    csrf = login.cookies[settings.AUTH_CSRF_COOKIE]
    bad_origin = auth_client.post(
        "/auth/refresh",
        cookies={
            settings.AUTH_REFRESH_COOKIE: refresh,
            settings.AUTH_CSRF_COOKIE: csrf,
        },
        headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
    )
    assert bad_origin.status_code == 403
    missing_csrf = auth_client.post(
        "/auth/refresh",
        cookies={
            settings.AUTH_REFRESH_COOKIE: refresh,
            settings.AUTH_CSRF_COOKIE: csrf,
        },
        headers={"Origin": "http://localhost:3000"},
    )
    assert missing_csrf.status_code == 403
    rotated = auth_client.post(
        "/auth/refresh",
        cookies={
            settings.AUTH_REFRESH_COOKIE: refresh,
            settings.AUTH_CSRF_COOKIE: csrf,
        },
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf},
    )
    assert rotated.status_code == 204
    replay = auth_client.post(
        "/auth/refresh",
        cookies={
            settings.AUTH_REFRESH_COOKIE: refresh,
            settings.AUTH_CSRF_COOKIE: csrf,
        },
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf},
    )
    assert replay.status_code == 401
    assert auth_client.post("/auth/logout").status_code == 204
    assert auth_client.post("/auth/logout").status_code == 204


def test_two_sessions_are_independent(auth_client: TestClient) -> None:
    first = _login(auth_client)
    first_cookies = {
        settings.AUTH_ACCESS_COOKIE: first.cookies[settings.AUTH_ACCESS_COOKIE],
        settings.AUTH_CSRF_COOKIE: first.cookies[settings.AUTH_CSRF_COOKIE],
    }
    second = _login(auth_client)
    second_access = second.cookies[settings.AUTH_ACCESS_COOKIE]
    response = auth_client.post(
        "/auth/logout",
        cookies=first_cookies,
        headers={
            "X-CSRF-Token": first_cookies[settings.AUTH_CSRF_COOKIE],
            "Origin": "http://localhost:3000",
        },
    )
    assert response.status_code == 204
    assert (
        auth_client.get("/auth/me", headers=_access_headers(second_access)).status_code
        == 200
    )


def test_disabled_user_invalidates_access(auth_client: TestClient) -> None:
    login = _login(auth_client)
    claims = jwt.decode(
        login.cookies[settings.AUTH_ACCESS_COOKIE], options={"verify_signature": False}
    )

    async def disable() -> None:
        factory = app.state.db_session_factory
        async with factory() as session:
            await session.execute(
                update(User)
                .where(User.id == uuid.UUID(claims["sub"]))
                .values(disabled_at=datetime.now(UTC))
            )
            await session.commit()

    asyncio.run(disable())
    assert (
        auth_client.get(
            "/auth/me",
            headers=_access_headers(login.cookies[settings.AUTH_ACCESS_COOKIE]),
        ).status_code
        == 401
    )


def test_login_without_origin_succeeds(auth_client: TestClient) -> None:
    request = auth_client.build_request(
        "POST",
        "/auth/login",
        json={"email": auth_client.auth_email, "password": auth_client.auth_password},  # type: ignore[attr-defined]
    )
    del request.headers["origin"]
    response = auth_client.send(request)

    assert response.status_code == 200
    assert settings.AUTH_ACCESS_COOKIE in response.cookies


def test_cookie_logout_without_origin_or_referer_is_forbidden(
    auth_client: TestClient,
) -> None:
    access = _login(auth_client).cookies[settings.AUTH_ACCESS_COOKIE]

    response = _post_without_origin(
        auth_client,
        "/auth/logout",
        {"X-CSRF-Token": auth_client.cookies[settings.AUTH_CSRF_COOKIE]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Origin is not allowed"
    auth_client.cookies.clear()
    assert (
        auth_client.get("/auth/me", headers=_access_headers(access)).status_code == 200
    )


def test_cookie_logout_with_an_allowed_referer_revokes_the_session(
    auth_client: TestClient,
) -> None:
    access = _login(auth_client).cookies[settings.AUTH_ACCESS_COOKIE]

    response = _post_without_origin(
        auth_client,
        "/auth/logout",
        {
            "Referer": "http://localhost:3000/users",
            "X-CSRF-Token": auth_client.cookies[settings.AUTH_CSRF_COOKIE],
        },
    )

    assert response.status_code == 204
    auth_client.cookies.clear()
    assert (
        auth_client.get("/auth/me", headers=_access_headers(access)).status_code == 401
    )
