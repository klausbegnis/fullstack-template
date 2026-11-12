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
from .clock import ClockDep, get_clock
from .database import SessionDep, get_auth_session, get_session
from .rate_limit import (
    RateLimitCounterDep,
    email_subject,
    get_rate_limit_counter,
    rate_limited,
)
from .users import SelfOrAdmin, UserServiceDep, get_user_service, require_self_or_admin

__all__ = [
    "AuthContextDep",
    "AuthServiceDep",
    "ClockDep",
    "CurrentUser",
    "RateLimitCounterDep",
    "RequireAdmin",
    "SelfOrAdmin",
    "SessionDep",
    "UserServiceDep",
    "email_subject",
    "get_auth_context",
    "get_auth_service",
    "get_auth_session",
    "get_clock",
    "get_current_user",
    "get_rate_limit_counter",
    "get_session",
    "get_user_service",
    "rate_limited",
    "require_admin",
    "require_self_or_admin",
]
