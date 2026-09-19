from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Depends

from app.core.exceptions import ForbiddenException
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from app.services.users import UserService

from .auth import CurrentUser
from .database import SessionDep


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session=session, users=UserRepository(session))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def require_self_or_admin(user_id: uuid.UUID, actor: CurrentUser) -> User:
    """Allow an admin to act on anyone, and any other user to act on themselves only."""
    if actor.role is not UserRole.ADMIN and actor.id != user_id:
        raise ForbiddenException()
    return actor


SelfOrAdmin = Annotated[User, Depends(require_self_or_admin)]

__all__ = [
    "SelfOrAdmin",
    "UserServiceDep",
    "get_user_service",
    "require_self_or_admin",
]
