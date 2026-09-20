"""FastAPI composition root and public dependency aliases."""

from .auth import (
    AuthContextDep,
    AuthServiceDep,
    CurrentUser,
    RequireAdmin,
    get_auth_context,
    get_auth_service,
    get_current_user,
    require_admin,
)
from .database import SessionDep, get_auth_session, get_session
from .users import SelfOrAdmin, UserServiceDep, get_user_service, require_self_or_admin

__all__ = [
    "AuthContextDep",
    "AuthServiceDep",
    "CurrentUser",
    "RequireAdmin",
    "SelfOrAdmin",
    "SessionDep",
    "UserServiceDep",
    "get_auth_context",
    "get_auth_service",
    "get_auth_session",
    "get_current_user",
    "get_session",
    "get_user_service",
    "require_admin",
    "require_self_or_admin",
]
