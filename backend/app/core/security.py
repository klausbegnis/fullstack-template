from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Any
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Response
import jwt

from app.config import Settings, settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, bool]:
    """Return (valid, needs_rehash), without exposing Argon2 errors."""
    try:
        valid = _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False, False
    return valid, _password_hasher.check_needs_rehash(password_hash)


async def hash_password_off_loop(password: str) -> str:
    """Hash a password in a worker thread so the event loop keeps serving.

    Argon2 burns tens of milliseconds of CPU per hash on an idle host and
    several hundred under load, while releasing the GIL. On the event loop that
    time stalls every other request of the process; in a thread it does not.
    Request paths use this; one-shot CLI commands keep `hash_password`.
    """
    return await asyncio.to_thread(hash_password, password)


async def verify_password_off_loop(
    password: str, password_hash: str
) -> tuple[bool, bool]:
    """Run `verify_password` in a worker thread, for the same reason as hashing."""
    return await asyncio.to_thread(verify_password, password, password_hash)


def new_secret() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def hash_secret(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def constant_time_equal(left: bytes | str, right: bytes | str) -> bool:
    if isinstance(left, str):
        left = left.encode()
    if isinstance(right, str):
        right = right.encode()
    return secrets.compare_digest(left, right)


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    now: datetime | None = None,
    config: Settings = settings,
) -> str:
    now = now or datetime.now(UTC)
    expires = now + timedelta(seconds=config.AUTH_ACCESS_TTL_SECONDS)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid.uuid4()),
        "iss": config.AUTH_JWT_ISSUER,
        "aud": config.AUTH_JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": expires,
    }
    return jwt.encode(
        claims, config.AUTH_JWT_SECRET.get_secret_value(), algorithm="HS256"
    )


def decode_access_token(token: str, *, config: Settings = settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        config.AUTH_JWT_SECRET.get_secret_value(),
        algorithms=["HS256"],
        issuer=config.AUTH_JWT_ISSUER,
        audience=config.AUTH_JWT_AUDIENCE,
        options={"require": ["sub", "sid", "jti", "iss", "aud", "iat", "nbf", "exp"]},
    )


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    *,
    config: Settings = settings,
) -> None:
    secure = (
        config.AUTH_COOKIE_SECURE
        if config.AUTH_COOKIE_SECURE is not None
        else not config.DEBUG
    )
    response.set_cookie(
        config.AUTH_ACCESS_COOKIE,
        access_token,
        max_age=config.AUTH_ACCESS_TTL_SECONDS,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        config.AUTH_REFRESH_COOKIE,
        refresh_token,
        max_age=config.AUTH_SESSION_TTL_SECONDS,
        path="/api/auth",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        config.AUTH_CSRF_COOKIE,
        csrf_token,
        max_age=config.AUTH_SESSION_TTL_SECONDS,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def clear_auth_cookies(response: Response, *, config: Settings = settings) -> None:
    secure = (
        config.AUTH_COOKIE_SECURE
        if config.AUTH_COOKIE_SECURE is not None
        else not config.DEBUG
    )
    response.delete_cookie(
        config.AUTH_ACCESS_COOKIE,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        config.AUTH_REFRESH_COOKIE,
        path="/api/auth",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        config.AUTH_CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="lax"
    )
