from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
import uuid

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import (
    constant_time_equal,
    create_access_token,
    decode_access_token,
    hash_password_off_loop,
    hash_secret,
    new_secret,
    verify_password_off_loop,
)
from app.core.transactions import transaction
from app.models.auth_session import AuthSession
from app.models.user import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.schemas.api.auth import AuthUserRead

_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$GxQNHil++9/g/0BYi5Ba5Q$SjSrOXFs"  # noqa: S105
    "GTJeIs1kQiEd7QespCArIXOGPjqok8pKro0"
)


@dataclass(frozen=True, slots=True)
class AuthRequestContext:
    """Authentication values extracted from the HTTP request at the boundary."""

    origin: str | None
    access_token: str | None
    refresh_token: str | None
    csrf_cookie: str | None
    csrf_header: str | None


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: AuthUserRead
    access_token: str
    refresh_token: str
    csrf_token: str


@dataclass(frozen=True, slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    csrf_token: str


def check_origin(origin: str | None, *, config: Settings = settings) -> None:
    """Reject an Origin header that CORS did not already allow."""
    if origin and origin not in config.CORS_ORIGINS:
        raise ForbiddenException("Origin is not allowed")


def request_origin(origin: str | None, referer: str | None) -> str | None:
    """Return the Origin header, else the `scheme://host[:port]` of the Referer."""
    if origin:
        return origin
    if not referer:
        return None
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc or "@" in parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def check_credentialed_origin(
    origin: str | None, referer: str | None, *, config: Settings = settings
) -> None:
    """Require an allowed origin on a mutation that carries a session cookie.

    The cookie is an ambient credential, so a request that proves no origin at
    all, neither Origin nor Referer, is refused rather than trusted.
    """
    resolved = request_origin(origin, referer)
    if resolved is None or resolved not in config.CORS_ORIGINS:
        raise ForbiddenException("Origin is not allowed")


def check_csrf(
    csrf_cookie: str | None,
    csrf_header: str | None,
    auth_session: AuthSession,
) -> None:
    """Enforce the double-submit CSRF contract for a mutating auth request."""
    if (
        not csrf_cookie
        or not csrf_header
        or not constant_time_equal(csrf_cookie, csrf_header)
        or not constant_time_equal(
            hash_secret(csrf_cookie), auth_session.csrf_token_hash
        )
    ):
        raise ForbiddenException("CSRF validation failed")


def to_auth_user(user: User) -> AuthUserRead:
    """Map a persisted identity to its public API representation."""
    return AuthUserRead(
        id=user.id,
        name=user.name or user.email.split("@", 1)[0],
        email=user.email,
        role=user.role,
    )


def split_refresh(value: str) -> tuple[uuid.UUID, str]:
    """Split an opaque `"{token_id}.{secret}"` refresh token."""
    try:
        token_id, secret = value.split(".", 1)
        if not secret:
            raise ValueError
        return uuid.UUID(token_id), secret
    except (ValueError, AttributeError):
        raise UnauthorizedException() from None


class AuthService:
    """Coordinate authentication use cases and their transaction boundaries."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        users: UserRepository,
        auth_sessions: AuthSessionRepository,
        config: Settings,
    ) -> None:
        self._session = session
        self._users = users
        self._auth_sessions = auth_sessions
        self._config = config

    async def to_auth_user(self, user: User) -> AuthUserRead:
        """Map a persisted identity to its public API representation."""
        return to_auth_user(user)

    async def login(self, email: str, password: str) -> LoginResult:
        """Authenticate a user and open a new session with fresh tokens."""
        user = await self._users.get_by_email(email)
        password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        valid, needs_rehash = await verify_password_off_loop(password, password_hash)
        if not user or not valid or user.disabled_at is not None:
            raise UnauthorizedException()
        now = datetime.now(UTC)
        csrf = new_secret()
        refresh_secret = new_secret()
        async with transaction(self._session):
            auth_session = await self._auth_sessions.create(
                user=user,
                csrf_hash=hash_secret(csrf),
                expires_at=now
                + timedelta(seconds=self._config.AUTH_SESSION_TTL_SECONDS),
            )
            refresh = await self._auth_sessions.add_refresh(
                auth_session=auth_session,
                secret_hash=hash_secret(refresh_secret),
                expires_at=now
                + timedelta(seconds=self._config.AUTH_SESSION_TTL_SECONDS),
            )
            if needs_rehash:
                user.password_hash = await hash_password_off_loop(password)
        access = create_access_token(
            user.id, auth_session.id, now=now, config=self._config
        )
        return LoginResult(
            user=to_auth_user(user),
            access_token=access,
            refresh_token=f"{refresh.id}.{refresh_secret}",
            csrf_token=csrf,
        )

    async def current_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> User:
        """Resolve the active user behind a validated access-token session."""
        auth_session = await self._auth_sessions.get_active(session_id)
        if not auth_session or auth_session.user_id != user_id:
            raise UnauthorizedException()
        user = await self._users.get_active(user_id)
        if not user:
            raise UnauthorizedException()
        return user

    async def refresh(self, context: AuthRequestContext) -> RefreshResult:
        """Rotate a refresh token, revoking its session on replay."""
        if not context.refresh_token:
            raise UnauthorizedException()
        token_id, secret = split_refresh(context.refresh_token)
        now = datetime.now(UTC)
        replay_detected = False
        result: RefreshResult | None = None
        async with transaction(self._session):
            token = await self._auth_sessions.get_token(token_id, for_update=True)
            auth_session = (
                await self._auth_sessions.get_active(token.session_id, for_update=True)
                if token
                else None
            )
            if token is None or auth_session is None:
                raise UnauthorizedException()
            invalid = (
                not constant_time_equal(hash_secret(secret), token.secret_hash)
                or token.consumed_at is not None
                or token.revoked_at is not None
                or token.expires_at <= now
            )
            if invalid:
                if token.consumed_at is not None or token.revoked_at is not None:
                    await self._auth_sessions.revoke(auth_session, "refresh_replay")
                    replay_detected = True
                else:
                    raise UnauthorizedException()
            if not replay_detected:
                check_csrf(
                    context.csrf_cookie,
                    context.csrf_header,
                    auth_session,
                )
                user = await self._users.get_active(auth_session.user_id)
                if not user:
                    await self._auth_sessions.revoke(auth_session, "user_disabled")
                    raise UnauthorizedException()
                token.consumed_at = now
                csrf = new_secret()
                refresh_secret = new_secret()
                auth_session.csrf_token_hash = hash_secret(csrf)
                successor = await self._auth_sessions.add_refresh(
                    auth_session=auth_session,
                    secret_hash=hash_secret(refresh_secret),
                    expires_at=auth_session.expires_at,
                )
                token.replaced_by_id = successor.id
                access = create_access_token(
                    user.id, auth_session.id, now=now, config=self._config
                )
                result = RefreshResult(
                    access_token=access,
                    refresh_token=f"{successor.id}.{refresh_secret}",
                    csrf_token=csrf,
                )
        if replay_detected or result is None:
            raise UnauthorizedException()
        return result

    async def logout(self, context: AuthRequestContext) -> None:
        """Revoke a session, including the refresh-token fallback path."""
        try:
            claims = decode_access_token(
                context.access_token or "", config=self._config
            )
            await self._logout_session(uuid.UUID(str(claims["sid"])), context)
            return
        except (jwt.PyJWTError, KeyError, ValueError):
            pass

        try:
            token_id, _ = split_refresh(context.refresh_token or "")
            token = await self._auth_sessions.get_token(token_id)
            if token:
                await self._logout_session(token.session_id, context)
            else:
                await self._session.rollback()
        except UnauthorizedException:
            await self._session.rollback()

    async def _logout_session(
        self, session_id: uuid.UUID, context: AuthRequestContext
    ) -> None:
        auth_session = await self._auth_sessions.get_by_id(session_id, for_update=True)
        if not auth_session or auth_session.revoked_at is not None:
            await self._session.rollback()
            return
        check_csrf(
            context.csrf_cookie,
            context.csrf_header,
            auth_session,
        )
        async with transaction(self._session):
            await self._auth_sessions.revoke(auth_session, "logout")
