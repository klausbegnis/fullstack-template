from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Depends, Request
import jwt

from app.config import SettingsDep
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthRequestContext, AuthService, check_origin

from .database import SessionDep


def _access_cookie(request: Request, cookie_name: str) -> str | None:
    value = request.cookies.get(cookie_name)
    if value:
        return value
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_auth_service(session: SessionDep, config: SettingsDep) -> AuthService:
    return AuthService(
        session=session,
        users=UserRepository(session),
        auth_sessions=AuthSessionRepository(session),
        config=config,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_auth_context(request: Request, config: SettingsDep) -> AuthRequestContext:
    context = AuthRequestContext(
        origin=request.headers.get("origin"),
        access_token=request.cookies.get(config.AUTH_ACCESS_COOKIE),
        refresh_token=request.cookies.get(config.AUTH_REFRESH_COOKIE),
        csrf_cookie=request.cookies.get(config.AUTH_CSRF_COOKIE),
        csrf_header=request.headers.get("x-csrf-token"),
    )
    check_origin(context.origin, config=config)
    return context


AuthContextDep = Annotated[AuthRequestContext, Depends(get_auth_context)]


async def get_current_user(
    request: Request, service: AuthServiceDep, config: SettingsDep
) -> User:
    token = _access_cookie(request, config.AUTH_ACCESS_COOKIE)
    if not token:
        raise UnauthorizedException()
    try:
        claims = decode_access_token(token, config=config)
        user_id = uuid.UUID(str(claims["sub"]))
        session_id = uuid.UUID(str(claims["sid"]))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise UnauthorizedException() from None
    return await service.current_user(session_id, user_id)


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
