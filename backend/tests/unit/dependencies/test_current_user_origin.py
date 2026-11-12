from __future__ import annotations

from collections.abc import Iterator
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.core.exceptions import APIException, api_exception_handler
from app.core.security import create_access_token
from app.dependencies.auth import (
    AuthContextDep,
    CurrentUser,
    get_auth_service,
)
from app.models.user import User
from tests.support.fakes import make_user

ALLOWED_ORIGIN = "http://localhost:3000"


class _ActiveSessionAuthService:
    def __init__(self, user: User) -> None:
        self._user = user

    async def current_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> User:
        return self._user


def _app(config: Settings, user: User) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(APIException, api_exception_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_auth_service] = lambda: _ActiveSessionAuthService(user)

    @app.get("/whoami")
    async def whoami(user: CurrentUser) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.post("/mutate")
    async def mutate(user: CurrentUser) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.post("/auth-action")
    async def auth_action(context: AuthContextDep) -> dict[str, bool]:
        return {"has_refresh": context.refresh_token is not None}

    return app


@pytest.fixture
def config() -> Settings:
    return Settings(TESTING=True, CORS_ORIGINS=[ALLOWED_ORIGIN])


@pytest.fixture
def token(config: Settings) -> str:
    return create_access_token(uuid.uuid4(), uuid.uuid4(), config=config)


@pytest.fixture
def client(config: Settings) -> Iterator[TestClient]:
    with TestClient(_app(config, make_user())) as test_client:
        yield test_client


def test_cookie_mutation_from_foreign_origin_is_forbidden(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    response = client.post(
        "/mutate",
        headers={"Origin": "https://evil.example", "Content-Type": "text/plain"},
        content="x",
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Origin is not allowed"


def test_cookie_mutation_from_allowed_origin_passes(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    assert client.post("/mutate", headers={"Origin": ALLOWED_ORIGIN}).status_code == 200


def test_cookie_mutation_without_origin_or_referer_is_forbidden(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    response = client.post("/mutate")

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Origin is not allowed"


def test_cookie_mutation_with_only_an_allowed_referer_passes(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    response = client.post(
        "/mutate", headers={"Referer": f"{ALLOWED_ORIGIN}/users?x=1"}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "referer",
    ["https://evil.example/users", f"http://user@{ALLOWED_ORIGIN[7:]}/", "not a url"],
    ids=["foreign", "userinfo", "malformed"],
)
def test_cookie_mutation_with_an_unproven_referer_is_forbidden(
    client: TestClient, config: Settings, token: str, referer: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    assert client.post("/mutate", headers={"Referer": referer}).status_code == 403


def test_foreign_origin_wins_over_an_allowed_referer(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    response = client.post(
        "/mutate",
        headers={"Origin": "https://evil.example", "Referer": f"{ALLOWED_ORIGIN}/"},
    )

    assert response.status_code == 403


def test_cookieless_auth_action_without_origin_passes(client: TestClient) -> None:
    assert client.post("/auth-action").status_code == 200


def test_cookieless_auth_action_from_foreign_origin_is_forbidden(
    client: TestClient,
) -> None:
    response = client.post("/auth-action", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403


def test_refresh_cookie_auth_action_without_origin_is_forbidden(
    client: TestClient, config: Settings
) -> None:
    client.cookies.set(config.AUTH_REFRESH_COOKIE, "token.secret")

    assert client.post("/auth-action").status_code == 403


def test_refresh_cookie_auth_action_from_allowed_origin_passes(
    client: TestClient, config: Settings
) -> None:
    client.cookies.set(config.AUTH_REFRESH_COOKIE, "token.secret")

    response = client.post("/auth-action", headers={"Origin": ALLOWED_ORIGIN})

    assert response.json() == {"has_refresh": True}


def test_cookie_read_from_foreign_origin_passes(
    client: TestClient, config: Settings, token: str
) -> None:
    client.cookies.set(config.AUTH_ACCESS_COOKIE, token)

    response = client.get("/whoami", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200


def test_bearer_mutation_skips_the_origin_check(client: TestClient, token: str) -> None:
    response = client.post(
        "/mutate",
        headers={
            "Origin": "https://evil.example",
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
