from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import uuid

import jwt
import pytest

from app.config import Settings
from app.core.exceptions import (
    ForbiddenException,
    RefreshSupersededException,
    UnauthorizedException,
)
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
from tests.support.fakes import FakeSession


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
        {**claims, "aud": "other"},
        config.AUTH_JWT_SECRET.get_secret_value(),
        algorithm="HS256",
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
            last_seen_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        self.refresh = AuthRefreshToken(
            id=uuid.uuid4(),
            session_id=self.auth_session.id,
            secret_hash=b"",
            created_at=datetime.now(UTC),
            expires_at=self.auth_session.expires_at,
        )
        self.issued: list[AuthRefreshToken] = []
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
        token = AuthRefreshToken(
            id=uuid.uuid4(),
            session_id=auth_session.id,
            secret_hash=secret_hash,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.issued.append(token)
        return token

    async def get_token(
        self, token_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthRefreshToken | None:
        del for_update
        tokens = [self.refresh, *self.issued]
        return next((token for token in tokens if token.id == token_id), None)

    async def get_by_id(
        self, session_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthSession | None:
        del for_update
        return self.auth_session if session_id == self.auth_session.id else None

    async def get_active(
        self, session_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthSession | None:
        del for_update
        if session_id != self.auth_session.id:
            return None
        if self.auth_session.revoked_at is not None:
            return None
        if self.auth_session.expires_at <= datetime.now(UTC):
            return None
        return self.auth_session

    async def revoke(self, auth_session: AuthSession, reason: str) -> None:
        auth_session.revoked_at = datetime.now(UTC)
        self.revocation_reason = reason


def _service_fixture() -> tuple[AuthService, FakeSession, _FakeAuthSessions, User, str]:
    password = "Correct horse battery staple 123!"
    user = User(
        id=uuid.uuid4(),
        email="Admin@Example.test",
        email_normalized="admin@example.test",
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session = FakeSession()
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


_IDLE = timedelta(days=14)


def _refresh_context(
    auth_sessions: _FakeAuthSessions, *, created_ago: timedelta, session_left: timedelta
) -> AuthRequestContext:
    now = datetime.now(UTC)
    secret = new_secret()
    csrf = new_secret()
    auth_sessions.auth_session.csrf_token_hash = hash_secret(csrf)
    auth_sessions.auth_session.expires_at = now + session_left
    auth_sessions.auth_session.last_seen_at = now - created_ago
    auth_sessions.refresh.secret_hash = hash_secret(secret)
    auth_sessions.refresh.created_at = now - created_ago
    auth_sessions.refresh.expires_at = now - created_ago + timedelta(days=30)
    return AuthRequestContext(
        origin="http://localhost:3000",
        access_token=None,
        refresh_token=f"{auth_sessions.refresh.id}.{secret}",
        csrf_cookie=csrf,
        csrf_header=csrf,
    )


def _assert_close(actual: datetime, expected: datetime) -> None:
    assert abs(actual - expected) < timedelta(seconds=5)


def test_refresh_rejects_a_token_idle_past_the_limit_without_revoking() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(days=15), session_left=timedelta(days=15)
    )

    with pytest.raises(UnauthorizedException):
        asyncio.run(service.refresh(context))

    assert auth_sessions.revocation_reason is None
    assert auth_sessions.auth_session.revoked_at is None
    assert auth_sessions.refresh.consumed_at is None
    assert auth_sessions.issued == []


def test_refresh_inside_the_idle_limit_caps_the_successor_at_the_idle_limit() -> None:
    service, session, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(days=13), session_left=timedelta(days=17)
    )

    result = asyncio.run(service.refresh(context))

    now = datetime.now(UTC)
    [successor] = auth_sessions.issued
    assert result.refresh_token.startswith(f"{successor.id}.")
    _assert_close(successor.expires_at, now + _IDLE)
    _assert_close(auth_sessions.auth_session.last_seen_at, now)
    assert auth_sessions.refresh.consumed_at is not None
    assert session.commits == 1


def test_refresh_successor_never_outlives_the_session_absolute_expiry() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(days=1), session_left=timedelta(days=1)
    )

    asyncio.run(service.refresh(context))

    [successor] = auth_sessions.issued
    assert successor.expires_at == auth_sessions.auth_session.expires_at


def test_refresh_accepts_a_token_issued_before_the_idle_limit() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(days=2), session_left=timedelta(days=28)
    )

    result = asyncio.run(service.refresh(context))

    assert result.refresh_token
    assert auth_sessions.revocation_reason is None


def test_login_caps_the_first_refresh_token_at_the_idle_limit() -> None:
    service, _, auth_sessions, user, password = _service_fixture()

    result = asyncio.run(service.login(user.email, password))

    now = datetime.now(UTC)
    [first] = auth_sessions.issued
    _assert_close(auth_sessions.auth_session.expires_at, now + timedelta(days=30))
    _assert_close(first.expires_at, now + _IDLE)
    _assert_close(
        result.access_expires_at,
        now + timedelta(seconds=Settings(TESTING=True).AUTH_ACCESS_TTL_SECONDS),
    )
    assert result.session_expires_at == auth_sessions.auth_session.expires_at


def test_current_user_accepts_a_session_used_inside_the_idle_limit() -> None:
    service, _, auth_sessions, user, _ = _service_fixture()
    auth_sessions.auth_session.last_seen_at = datetime.now(UTC) - timedelta(days=13)

    resolved = asyncio.run(service.current_user(auth_sessions.auth_session.id, user.id))

    assert resolved is user


def test_current_user_rejects_a_session_idle_past_the_limit() -> None:
    service, _, auth_sessions, user, _ = _service_fixture()
    auth_sessions.auth_session.last_seen_at = datetime.now(UTC) - timedelta(days=15)

    with pytest.raises(UnauthorizedException):
        asyncio.run(service.current_user(auth_sessions.auth_session.id, user.id))


def _rotate_and_age(
    service: AuthService,
    auth_sessions: _FakeAuthSessions,
    context: AuthRequestContext,
    *,
    seconds: int,
) -> None:
    asyncio.run(service.refresh(context))
    auth_sessions.refresh.consumed_at = datetime.now(UTC) - timedelta(seconds=seconds)


def test_refresh_returns_the_access_and_session_expiry() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(days=1), session_left=timedelta(days=5)
    )

    result = asyncio.run(service.refresh(context))

    _assert_close(
        result.access_expires_at,
        datetime.now(UTC)
        + timedelta(seconds=Settings(TESTING=True).AUTH_ACCESS_TTL_SECONDS),
    )
    assert result.session_expires_at == auth_sessions.auth_session.expires_at


def test_refresh_superseded_inside_the_grace_window_keeps_the_session() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(minutes=1), session_left=timedelta(days=5)
    )
    _rotate_and_age(service, auth_sessions, context, seconds=2)

    with pytest.raises(RefreshSupersededException):
        asyncio.run(service.refresh(context))

    assert auth_sessions.revocation_reason is None
    assert auth_sessions.auth_session.revoked_at is None


def test_refresh_reused_after_the_grace_window_revokes_the_session() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(minutes=1), session_left=timedelta(days=5)
    )
    _rotate_and_age(service, auth_sessions, context, seconds=16)

    with pytest.raises(UnauthorizedException) as raised:
        asyncio.run(service.refresh(context))

    assert not isinstance(raised.value, RefreshSupersededException)
    assert auth_sessions.revocation_reason == "refresh_replay"


def test_refresh_reused_after_the_successor_was_used_revokes_the_session() -> None:
    service, _, auth_sessions, _, _ = _service_fixture()
    context = _refresh_context(
        auth_sessions, created_ago=timedelta(minutes=1), session_left=timedelta(days=5)
    )
    _rotate_and_age(service, auth_sessions, context, seconds=2)
    auth_sessions.issued[0].consumed_at = datetime.now(UTC)

    with pytest.raises(UnauthorizedException) as raised:
        asyncio.run(service.refresh(context))

    assert not isinstance(raised.value, RefreshSupersededException)
    assert auth_sessions.revocation_reason == "refresh_replay"
