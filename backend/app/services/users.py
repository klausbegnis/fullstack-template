from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password_off_loop
from app.core.transactions import transaction
from app.models.user import User, UserRole
from app.repositories.security_events import SecurityEventRepository
from app.repositories.users import UserRepository
from app.schemas.api.users import UserCreate, UserListFilters, UserRead, UserUpdate
from app.services.security_audit import (
    ROLE_CHANGED,
    USER_CREATED,
    USER_DISABLED,
    USER_UPDATED,
    record_security_event,
)


def normalize_name(name: str) -> str:
    """Collapse internal whitespace and trim a display name."""
    return re.sub(r"\s+", " ", name.strip())


def to_user_read(user: User) -> UserRead:
    """Map a persisted identity to its public API representation."""
    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        disabled_at=user.disabled_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class UserService:
    """Coordinate user-management use cases and their transaction boundaries."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        users: UserRepository,
        security_events: SecurityEventRepository,
    ) -> None:
        self._session = session
        self._users = users
        self._security_events = security_events

    async def list_users(self, filters: UserListFilters) -> tuple[list[UserRead], int]:
        users, total = await self._users.list(
            offset=filters.offset, limit=filters.page_size
        )
        return [to_user_read(user) for user in users], total

    async def get_user(self, user_id: uuid.UUID) -> UserRead:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundException("User not found")
        return to_user_read(user)

    async def create_user(self, actor: User, payload: UserCreate) -> UserRead:
        name = normalize_name(payload.name)
        if not name:
            raise ValidationException("User name cannot be empty", {"field": "name"})
        try:
            async with transaction(self._session):
                user = await self._users.create(
                    name=name,
                    email=payload.email,
                    password_hash=await hash_password_off_loop(payload.password),
                )
                if payload.role is not UserRole.MEMBER:
                    await self._users.update(user, role=payload.role)
                await record_security_event(
                    self._security_events,
                    action=USER_CREATED,
                    user_id=user.id,
                    actor_user_id=actor.id,
                    payload={"role": user.role.value},
                )
        except IntegrityError:
            raise ConflictException("A user with this email already exists") from None
        return to_user_read(user)

    async def update_user(
        self, actor: User, user_id: uuid.UUID, payload: UserUpdate
    ) -> UserRead:
        if payload.role is not None and actor.role is not UserRole.ADMIN:
            raise ForbiddenException("Only an administrator may change a role")
        try:
            async with transaction(self._session):
                user = await self._users.get_for_update(user_id)
                if user is None:
                    raise NotFoundException("User not found")
                name = (
                    normalize_name(payload.name) if payload.name is not None else None
                )
                if payload.name is not None and not name:
                    raise ValidationException(
                        "User name cannot be empty", {"field": "name"}
                    )
                await self._guard_last_admin_demotion(user, payload.role)
                old_role = user.role
                await self._users.update(
                    user, name=name, email=payload.email, role=payload.role
                )
                await self._record_update(actor, user, payload, old_role)
        except IntegrityError:
            raise ConflictException("A user with this email already exists") from None
        return to_user_read(user)

    async def disable_user(self, actor: User, user_id: uuid.UUID) -> UserRead:
        async with transaction(self._session):
            user = await self._users.get_for_update(user_id)
            if user is None:
                raise NotFoundException("User not found")
            await self._guard_last_admin_disable(user)
            await self._users.disable(user)
            await record_security_event(
                self._security_events,
                action=USER_DISABLED,
                user_id=user.id,
                actor_user_id=actor.id,
            )
        return to_user_read(user)

    async def _record_update(
        self, actor: User, user: User, payload: UserUpdate, old_role: UserRole
    ) -> None:
        """Record which profile fields changed, and a role change on its own."""
        fields = sorted(
            field for field in ("name", "email") if getattr(payload, field) is not None
        )
        if fields:
            await record_security_event(
                self._security_events,
                action=USER_UPDATED,
                user_id=user.id,
                actor_user_id=actor.id,
                payload={"fields": fields},
            )
        if payload.role is not None and payload.role is not old_role:
            await record_security_event(
                self._security_events,
                action=ROLE_CHANGED,
                user_id=user.id,
                actor_user_id=actor.id,
                payload={"old_role": old_role.value, "role": payload.role.value},
            )

    async def _guard_last_admin_demotion(
        self, user: User, new_role: UserRole | None
    ) -> None:
        is_demotion = (
            new_role is not None
            and new_role is not UserRole.ADMIN
            and user.role is UserRole.ADMIN
            and user.disabled_at is None
        )
        if is_demotion and await self._users.count_active_admins(for_update=True) <= 1:
            raise ValidationException(
                "The last remaining active administrator cannot be demoted"
            )

    async def _guard_last_admin_disable(self, user: User) -> None:
        is_active_admin = user.role is UserRole.ADMIN and user.disabled_at is None
        if (
            is_active_admin
            and await self._users.count_active_admins(for_update=True) <= 1
        ):
            raise ValidationException(
                "The last remaining active administrator cannot be disabled"
            )


__all__ = ["UserService", "normalize_name", "to_user_read"]
