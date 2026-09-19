from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import uuid

import jwt
import pytest

from app.config import Settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import (
    constant_time_equal,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_secret,
    new_secret,
    verify_password,
)
from app.models.auth_session import AuthRefreshToken, AuthSession
from app.models.user import User, UserRole
from app.services.auth import (
    AuthRequestContext,
    AuthService,
    check_csrf,
    check_origin,
    split_refresh,
)


def test_argon2_passwords_and_rehash_contract() -> None:
    password_hash = hash_password("secret")
    assert password_hash.startswith("$argon2id$")
    assert verify_password("secret", password_hash)[0]
    assert not verify_password("wrong", password_hash)[0]
    assert not verify_password("secret", "not-a-phc-hash")[0]


def test_access_claims_are_complete_and_strictly_validated() -> None:
    config = Settings(TESTING=True)
    user_id, session_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id, session_id, config=config)
    claims = decode_access_token(token, config=config)
    assert {"sub", "sid", "jti", "iss", "aud", "iat", "nbf", "exp"} <= claims.keys()
    altered = jwt.encode(
        {**claims, "aud": "other"}, config.AUTH_JWT_SECRET, algorithm="HS256"
    )
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(altered, config=config)


def test_opaque_refresh_secret_is_random_and_split() -> None:
    token_id = uuid.uuid4()
    secret = new_secret()
    parsed_id, parsed_secret = split_refresh(f"{token_id}.{secret}")
    assert parsed_id == token_id
    assert constant_time_equal(parsed_secret, secret)
    with pytest.raises(UnauthorizedException):
        split_refresh("not-a-refresh-token")
    assert len(hash_secret(secret)) == 32


def test_csrf_requires_double_submit_and_origin_allowlist() -> None:
    csrf = new_secret()
    auth_session = AuthSession(
        csrf_token_hash=hash_secret(csrf),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    check_csrf(csrf, csrf, auth_session)
    with pytest.raises(ForbiddenException):
        check_csrf(csrf, "wrong", auth_session)
    with pytest.raises(ForbiddenException):
        check_csrf(None, None, auth_session)
    with pytest.raises(ForbiddenException):
        check_origin("https://evil.example")


def test_auth_user_contract_has_no_tenant_concept() -> None:
    from app.services.auth import to_auth_user

    user = User(
        id=uuid.uuid4(),
        email="Admin@Example.test",
        email_normalized="admin@example.test",
        password_hash=hash_password("secret"),
        role=UserRole.ADMIN,
    )
    output = to_auth_user(user)
    assert output.role is UserRole.ADMIN
    assert output.name == "Admin"


class _FakeTransaction:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        self._session._in_transaction = True
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        return False


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self._in_transaction = False

    def in_transaction(self) -> bool:
        return self._in_transaction

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def commit(self) -> None:
        self.commits += 1
        self._in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._in_transaction = False


class _FakeUsers:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_by_email(self, email: str) -> User | None:
        return self.user if email.lower() == self.user.email_normalized else None

    async def get_active(self, user_id: uuid.UUID) -> User | None:
        return self.user if user_id == self.user.id else None


class _FakeAuthSessions:
    def __init__(self, user: User) -> None:
        self.auth_session = AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            csrf_token_hash=b"",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        self.refresh = AuthRefreshToken(
            id=uuid.uuid4(),
            session_id=self.auth_session.id,
            secret_hash=b"",
            expires_at=self.auth_session.expires_at,
        )
        self.revocation_reason: str | None = None

    async def create(
        self, *, user: User, csrf_hash: bytes, expires_at: datetime
    ) -> AuthSession:
        self.auth_session.user_id = user.id
        self.auth_session.csrf_token_hash = csrf_hash
        self.auth_session.expires_at = expires_at
        return self.auth_session

    async def add_refresh(
        self,
        *,
        auth_session: AuthSession,
        secret_hash: bytes,
        expires_at: datetime,
    ) -> AuthRefreshToken:
        self.refresh.session_id = auth_session.id
        self.refresh.secret_hash = secret_hash
        self.refresh.expires_at = expires_at
        return self.refresh

    async def get_token(
        self, token_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthRefreshToken | None:
        del for_update
        return self.refresh if token_id == self.refresh.id else None

    async def get_by_id(
        self, session_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthSession | None:
        del for_update
        return self.auth_session if session_id == self.auth_session.id else None

    async def revoke(self, auth_session: AuthSession, reason: str) -> None:
        auth_session.revoked_at = datetime.now(UTC)
        self.revocation_reason = reason


def _service_fixture() -> tuple[
    AuthService, _FakeSession, _FakeAuthSessions, User, str
]:
    password = "Correct horse battery staple 123!"
    user = User(
        id=uuid.uuid4(),
        email="Admin@Example.test",
        email_normalized="admin@example.test",
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session = _FakeSession()
    auth_sessions = _FakeAuthSessions(user)
    service = AuthService(
        session=session,  # type: ignore[arg-type]
        users=_FakeUsers(user),  # type: ignore[arg-type]
        auth_sessions=auth_sessions,  # type: ignore[arg-type]
        config=Settings(TESTING=True),
    )
    return service, session, auth_sessions, user, password


def test_auth_service_login_owns_transaction_and_returns_cookie_values() -> None:
    service, session, _, user, password = _service_fixture()
    result = asyncio.run(service.login(user.email, password))

    assert result.user.id == user.id
    assert result.access_token
    assert result.refresh_token
    assert result.csrf_token
    assert session.commits == 1


def test_logout_refresh_fallback_is_owned_by_auth_service() -> None:
    service, session, auth_sessions, _, _ = _service_fixture()
    csrf = new_secret()
    auth_sessions.auth_session.csrf_token_hash = hash_secret(csrf)
    context = AuthRequestContext(
        origin="http://localhost:3000",
        access_token="invalid",
        refresh_token=f"{auth_sessions.refresh.id}.secret",
        csrf_cookie=csrf,
        csrf_header=csrf,
    )

    asyncio.run(service.logout(context))

    assert auth_sessions.revocation_reason == "logout"
    assert session.commits == 1
