from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Depends, Request
import jwt

from app.config import Settings, SettingsDep
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.security_events import SecurityEventRepository
from app.repositories.users import UserRepository
from app.services.auth import (
    AuthRequestContext,
    AuthService,
    check_credentialed_origin,
    check_origin,
)

from .database import SessionDep

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _check_cookie_mutation_origin(request: Request, config: Settings) -> None:
    check_credentialed_origin(
        request.headers.get("origin"), request.headers.get("referer"), config=config
    )


def _carries_session_cookie(request: Request, config: Settings) -> bool:
    return bool(
        request.cookies.get(config.AUTH_ACCESS_COOKIE)
        or request.cookies.get(config.AUTH_REFRESH_COOKIE)
    )


def _access_token(request: Request, config: Settings) -> str | None:
    """Return the access token, origin-checking a cookie that rides a mutation.

    The cookie is an ambient credential a same-site page can make the browser
    send, so a state-changing request carrying it must prove an allowed origin
    through Origin or, failing that, Referer. A bearer token is never ambient
    and needs no such check.
    """
    cookie = request.cookies.get(config.AUTH_ACCESS_COOKIE)
    if not cookie:
        return _bearer_token(request)
    if request.method not in SAFE_METHODS:
        _check_cookie_mutation_origin(request, config)
    return cookie


def get_auth_service(session: SessionDep, config: SettingsDep) -> AuthService:
    return AuthService(
        session=session,
        users=UserRepository(session),
        auth_sessions=AuthSessionRepository(session),
        security_events=SecurityEventRepository(session),
        config=config,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_auth_context(request: Request, config: SettingsDep) -> AuthRequestContext:
    """Extract auth values; refuse a cookie-carrying mutation without an allowed origin.

    A cookie-less request, such as the server-side login call, keeps the lenient
    rule: only a present Origin outside the allowlist is refused.
    """
    if request.method not in SAFE_METHODS and _carries_session_cookie(request, config):
        _check_cookie_mutation_origin(request, config)
    else:
        check_origin(request.headers.get("origin"), config=config)
    return AuthRequestContext(
        origin=request.headers.get("origin"),
        access_token=request.cookies.get(config.AUTH_ACCESS_COOKIE),
        refresh_token=request.cookies.get(config.AUTH_REFRESH_COOKIE),
        csrf_cookie=request.cookies.get(config.AUTH_CSRF_COOKIE),
        csrf_header=request.headers.get("x-csrf-token"),
    )


AuthContextDep = Annotated[AuthRequestContext, Depends(get_auth_context)]


async def get_current_user(
    request: Request, service: AuthServiceDep, config: SettingsDep
) -> User:
    token = _access_token(request, config)
    if not token:
        raise UnauthorizedException()
    try:
        claims = decode_access_token(token, config=config)
        user_id = uuid.UUID(str(claims["sub"]))
        session_id = uuid.UUID(str(claims["sid"]))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise UnauthorizedException() from None
    user = await service.current_user(session_id, user_id)
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenException()
    return user


RequireAdmin = Annotated[User, Depends(require_admin)]

__all__ = [
    "AuthContextDep",
    "AuthServiceDep",
    "CurrentUser",
    "RequireAdmin",
    "get_auth_context",
    "get_auth_service",
    "get_current_user",
    "require_admin",
]
