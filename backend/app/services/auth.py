from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
import uuid

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.exceptions import (
    ForbiddenException,
    RefreshSupersededException,
    UnauthorizedException,
)
from app.core.logger import get_logger
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
from app.models.auth_session import AuthRefreshToken, AuthSession
from app.models.user import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.security_events import SecurityEventRepository
from app.repositories.users import UserRepository
from app.schemas.api.auth import AuthUserRead
from app.services.security_audit import (
    LOGIN_FAILED,
    LOGIN_SUCCEEDED,
    LOGOUT,
    REFRESH_TOKEN_REUSED,
    record_security_event,
)

logger = get_logger(__name__)

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
    access_expires_at: datetime
    session_expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    session_expires_at: datetime


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


def access_token_expiry(now: datetime, config: Settings) -> datetime:
    """Return when an access token issued at `now` stops being accepted."""
    return now + timedelta(seconds=config.AUTH_ACCESS_TTL_SECONDS)


def refresh_token_expiry(
    session_expires_at: datetime, now: datetime, config: Settings
) -> datetime:
    """Return when a refresh token issued at `now` stops being usable.

    The token lives until the earlier of the session's absolute expiry and the
    idle limit counted from `now`, so an unused session ends after the idle
    limit while a used one still ends at its absolute expiry.
    """
    idle_expires_at = now + timedelta(seconds=config.AUTH_SESSION_IDLE_TTL_SECONDS)
    return min(session_expires_at, idle_expires_at)


def idle_cutoff(now: datetime, config: Settings) -> datetime:
    """Return the instant before which an unused session counts as idle."""
    return now - timedelta(seconds=config.AUTH_SESSION_IDLE_TTL_SECONDS)


class AuthService:
    """Coordinate authentication use cases and their transaction boundaries."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        users: UserRepository,
        auth_sessions: AuthSessionRepository,
        security_events: SecurityEventRepository,
        config: Settings,
    ) -> None:
        self._session = session
        self._users = users
        self._auth_sessions = auth_sessions
        self._security_events = security_events
        self._config = config

    async def to_auth_user(self, user: User) -> AuthUserRead:
        """Map a persisted identity to its public API representation."""
        return to_auth_user(user)

    async def login(self, email: str, password: str) -> LoginResult:
        """Authenticate a user and open a new session with fresh tokens."""
        user = await self._users.get_by_email(email)
        password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        valid, needs_rehash = await verify_password_off_loop(password, password_hash)
        if user is None:
            logger.warning("login failed for an unknown account")
            raise UnauthorizedException()
        if not valid or user.disabled_at is not None:
            await self._record_login_failure(user, password_valid=valid)
            raise UnauthorizedException()
        now = datetime.now(UTC)
        csrf = new_secret()
        refresh_secret = new_secret()
        session_expires_at = now + timedelta(
            seconds=self._config.AUTH_SESSION_TTL_SECONDS
        )
        async with transaction(self._session):
            auth_session = await self._auth_sessions.create(
                user=user,
                csrf_hash=hash_secret(csrf),
                expires_at=session_expires_at,
            )
            refresh = await self._auth_sessions.add_refresh(
                auth_session=auth_session,
                secret_hash=hash_secret(refresh_secret),
                expires_at=refresh_token_expiry(session_expires_at, now, self._config),
            )
            if needs_rehash:
                user.password_hash = await hash_password_off_loop(password)
            await record_security_event(
                self._security_events,
                action=LOGIN_SUCCEEDED,
                user_id=user.id,
                actor_user_id=user.id,
            )
        access = create_access_token(
            user.id, auth_session.id, now=now, config=self._config
        )
        return LoginResult(
            user=to_auth_user(user),
            access_token=access,
            refresh_token=f"{refresh.id}.{refresh_secret}",
            csrf_token=csrf,
            access_expires_at=access_token_expiry(now, self._config),
            session_expires_at=session_expires_at,
        )

    async def _record_login_failure(self, user: User, *, password_valid: bool) -> None:
        """Commit a failed sign-in for a known user before the caller refuses it."""
        reason = "disabled" if password_valid else "invalid_password"
        async with transaction(self._session):
            await record_security_event(
                self._security_events,
                action=LOGIN_FAILED,
                user_id=user.id,
                actor_user_id=user.id,
                payload={"reason": reason},
            )

    async def current_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> User:
        """Resolve the active user behind a validated access-token session.

        A session unused for longer than the idle limit is refused even while
        its access token is still within its own lifetime.
        """
        auth_session = await self._auth_sessions.get_active(session_id)
        if (
            not auth_session
            or auth_session.user_id != user_id
            or auth_session.last_seen_at <= idle_cutoff(datetime.now(UTC), self._config)
        ):
            raise UnauthorizedException()
        user = await self._users.get_active(user_id)
        if not user:
            raise UnauthorizedException()
        return user

    async def refresh(self, context: AuthRequestContext) -> RefreshResult:
        """Rotate a refresh token, revoking its session on replay.

        A token unused for longer than the idle limit is refused without
        revoking anything; a genuine token a sibling request rotated within
        the grace window raises `RefreshSupersededException` and keeps the
        session.
        """
        if not context.refresh_token:
            raise UnauthorizedException()
        token_id, secret = split_refresh(context.refresh_token)
        now = datetime.now(UTC)
        cutoff = idle_cutoff(now, self._config)
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
                or token.created_at <= cutoff
            )
            if invalid:
                if await self._is_superseded(token, secret, now):
                    raise RefreshSupersededException()
                if token.consumed_at is not None or token.revoked_at is not None:
                    await self._auth_sessions.revoke(auth_session, "refresh_replay")
                    await record_security_event(
                        self._security_events,
                        action=REFRESH_TOKEN_REUSED,
                        user_id=auth_session.user_id,
                        actor_user_id=None,
                    )
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
                auth_session.last_seen_at = now
                csrf = new_secret()
                refresh_secret = new_secret()
                auth_session.csrf_token_hash = hash_secret(csrf)
                successor = await self._auth_sessions.add_refresh(
                    auth_session=auth_session,
                    secret_hash=hash_secret(refresh_secret),
                    expires_at=refresh_token_expiry(
                        auth_session.expires_at, now, self._config
                    ),
                )
                token.replaced_by_id = successor.id
                access = create_access_token(
                    user.id, auth_session.id, now=now, config=self._config
                )
                result = RefreshResult(
                    access_token=access,
                    refresh_token=f"{successor.id}.{refresh_secret}",
                    csrf_token=csrf,
                    access_expires_at=access_token_expiry(now, self._config),
                    session_expires_at=auth_session.expires_at,
                )
        if replay_detected or result is None:
            raise UnauthorizedException()
        return result

    async def _is_superseded(
        self, token: AuthRefreshToken, secret: str, now: datetime
    ) -> bool:
        """Tell a concurrent refresh that lost the rotation race from a replay.

        The token must be genuine, rotated less than the grace window ago and
        not revoked, and its successor must still be unused: then a sibling
        request or tab won the rotation and the session stays valid.
        """
        if (
            token.consumed_at is None
            or token.revoked_at is not None
            or token.replaced_by_id is None
            or not constant_time_equal(hash_secret(secret), token.secret_hash)
            or now - token.consumed_at
            >= timedelta(seconds=self._config.AUTH_REFRESH_GRACE_SECONDS)
        ):
            return False
        successor = await self._auth_sessions.get_token(token.replaced_by_id)
        return (
            successor is not None
            and successor.consumed_at is None
            and successor.revoked_at is None
        )

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
            await record_security_event(
                self._security_events,
                action=LOGOUT,
                user_id=auth_session.user_id,
                actor_user_id=auth_session.user_id,
            )
