from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRepository:
    """Persist users through one request-scoped database session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        total = await self._session.scalar(select(func.count()).select_from(User))
        rows = await self._session.scalars(
            select(User).order_by(User.created_at, User.id).offset(offset).limit(limit)
        )
        return list(rows.all()), total or 0

    async def count_active_admins(self, *, for_update: bool = False) -> int:
        query = select(User.id).where(
            User.role == UserRole.ADMIN, User.disabled_at.is_(None)
        )
        if for_update:
            query = query.with_for_update()
        result = await self._session.scalars(query)
        return len(result.all())

    async def get_by_email(self, email: str) -> User | None:
        result: User | None = await self._session.scalar(
            select(User).where(User.email_normalized == normalize_email(email))
        )
        return result

    async def get_active(self, user_id: uuid.UUID) -> User | None:
        result: User | None = await self._session.scalar(
            select(User).where(User.id == user_id, User.disabled_at.is_(None))
        )
        return result

    async def get_for_update(self, user_id: uuid.UUID) -> User | None:
        result: User | None = await self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        return result

    async def create(self, *, name: str, email: str, password_hash: str) -> User:
        user = User(
            name=name,
            email=email.strip(),
            email_normalized=normalize_email(email),
            password_hash=password_hash,
            role=UserRole.MEMBER,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def create_bootstrap_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.ADMIN,
    ) -> User:
        normalized = normalize_email(email)
        existing = await self.get_by_email(normalized)
        if existing:
            return existing
        user = User(
            email=email.strip(),
            email_normalized=normalized,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(
        self,
        user: User,
        *,
        name: str | None = None,
        email: str | None = None,
        role: UserRole | None = None,
    ) -> User:
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email.strip()
            user.email_normalized = normalize_email(email)
        if role is not None:
            user.role = role
        user.updated_at = datetime.now(UTC)
        await self._session.flush()
        return user

    async def disable(self, user: User) -> User:
        user.disabled_at = datetime.now(UTC)
        user.updated_at = datetime.now(UTC)
        await self._session.flush()
        return user

    async def touch(self, user: User) -> None:
        user.updated_at = datetime.now(UTC)

    async def promote_admin(self, user: User) -> User:
        user.role = UserRole.ADMIN
        user.updated_at = datetime.now(UTC)
        await self._session.flush()
        return user
