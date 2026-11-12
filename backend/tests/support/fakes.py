"""Hand-written doubles shared by the unit tier.

Unit tests use fakes rather than mocks so a collaborator's signature change
breaks the double instead of leaving an assertion that silently still passes.
`FakeSession` records commit and rollback counts, which is how a service test
proves it owns exactly one transaction boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.security_event import SecurityEvent
from app.models.user import User, UserRole
from app.repositories.users import normalize_email


class FakeSession:
    """Minimal `AsyncSession` substitute that counts transaction outcomes."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self._in_transaction = False

    def in_transaction(self) -> bool:
        return self._in_transaction

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self)

    def enter_transaction(self) -> None:
        """Mark the session as having an in-flight transaction."""
        self._in_transaction = True

    async def commit(self) -> None:
        self.commits += 1
        self._in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._in_transaction = False


class FakeTransaction:
    """Async context manager mirroring `AsyncSession.begin()`."""

    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        self._session.enter_transaction()
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        return False


def make_user(*, role: UserRole = UserRole.MEMBER, disabled: bool = False) -> User:
    """Build a persisted-looking user without touching a database."""
    return User(
        id=uuid.uuid4(),
        name="Existing User",
        email="existing@example.test",
        email_normalized="existing@example.test",
        password_hash=hash_password("Correct horse battery staple 123!"),
        role=role,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        disabled_at=datetime.now(UTC) if disabled else None,
    )


class FakeUserRepository:
    """In-memory stand-in for `UserRepository` keyed by user id."""

    def __init__(self, users: list[User], *, fail_on_create: bool = False) -> None:
        self._users = {user.id: user for user in users}
        self._fail_on_create = fail_on_create

    async def get(self, user_id: uuid.UUID) -> User | None:
        return self._users.get(user_id)

    async def get_for_update(self, user_id: uuid.UUID) -> User | None:
        return self._users.get(user_id)

    async def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        ordered = sorted(self._users.values(), key=lambda user: user.created_at)
        return ordered[offset : offset + limit], len(ordered)

    async def count_active_admins(self, *, for_update: bool = False) -> int:
        del for_update
        return sum(
            1
            for user in self._users.values()
            if user.role is UserRole.ADMIN and user.disabled_at is None
        )

    async def create(self, *, name: str, email: str, password_hash: str) -> User:
        if self._fail_on_create:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            email_normalized=normalize_email(email),
            password_hash=password_hash,
            role=UserRole.MEMBER,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._users[user.id] = user
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
            user.email = email
            user.email_normalized = normalize_email(email)
        if role is not None:
            user.role = role
        return user

    async def disable(self, user: User) -> User:
        user.disabled_at = datetime.now(UTC)
        return user


class FakeSecurityEventRepository:
    """In-memory stand-in for `SecurityEventRepository` keeping appended events."""

    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    async def append(
        self,
        *,
        action: str,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        payload: dict[str, object],
    ) -> SecurityEvent:
        event = SecurityEvent(
            id=uuid.uuid4(),
            action=action,
            user_id=user_id,
            actor_user_id=actor_user_id,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event

    @property
    def actions(self) -> list[str]:
        """Return the recorded actions in order."""
        return [event.action for event in self.events]
