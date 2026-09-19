from __future__ import annotations

import ast
from pathlib import Path
from typing import get_args
import uuid

from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import (
    AuthServiceDep,
    SessionDep,
    get_auth_service,
    get_auth_session,
    get_session,
)
from app.main import app
from app.models.user import UserRole
from app.schemas.api.auth import AuthUserRead
from app.services.auth import AuthService, LoginResult


def test_auth_router_does_not_import_persistence_details() -> None:
    router_path = Path(__file__).parents[3] / "app" / "routers" / "auth.py"
    tree = ast.parse(router_path.read_text())
    forbidden = ("app.repositories", "app.models", "sqlalchemy")

    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imported_modules
        for prefix in forbidden
    )


def test_auth_service_dependency_is_non_optional_and_uses_central_session() -> None:
    assert get_args(AuthServiceDep)[0] is AuthService
    assert get_auth_session is get_session
    assert get_args(SessionDep)[0].__name__ == "AsyncSession"


def test_auth_service_provider_can_be_overridden_at_http_boundary() -> None:
    class FakeAuthService:
        def __init__(self) -> None:
            self.credentials: tuple[str, str] | None = None

        async def login(self, email: str, password: str) -> LoginResult:
            self.credentials = (email, password)
            return LoginResult(
                user=AuthUserRead(
                    id=uuid.uuid4(),
                    name="provider-test",
                    email=email,
                    role=UserRole.MEMBER,
                ),
                access_token="access",
                refresh_token=f"{uuid.uuid4()}.refresh",
                csrf_token="csrf",
            )

    fake = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: fake
    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": "override@example.test", "password": "secret"},
                headers={"Origin": "http://localhost:3000"},
            )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    assert response.json()["email"] == "override@example.test"
    assert fake.credentials == ("override@example.test", "secret")
    assert settings.AUTH_ACCESS_COOKIE in response.cookies


def test_database_composition_failure_uses_sanitized_500() -> None:
    def unavailable_session() -> None:
        raise RuntimeError("database unavailable with sensitive detail")

    app.dependency_overrides[get_session] = unavailable_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/auth/login",
                json={"email": "user@example.test", "password": "secret"},
                headers={"Origin": "http://localhost:3000"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 500
    body = response.json()
    request_id = body.pop("request_id")
    assert isinstance(request_id, str) and request_id
    assert body == {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred",
        }
    }
    assert "sensitive detail" not in response.text
