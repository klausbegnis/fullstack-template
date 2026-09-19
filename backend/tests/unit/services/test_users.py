from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.users import normalize_email
from app.schemas.api.users import UserCreate, UserListFilters, UserUpdate
from app.services.users import UserService, normalize_name


class _FakeTransaction:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        self._session._in_transaction = True
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        return False


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self._in_transaction = False

    def in_transaction(self) -> bool:
        return self._in_transaction

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def commit(self) -> None:
        self.commits += 1
        self._in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._in_transaction = False


def _make_user(*, role: UserRole = UserRole.MEMBER, disabled: bool = False) -> User:
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


class _FakeUserRepository:
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


def _service(users: list[User], **kwargs: bool) -> tuple[UserService, _FakeSession]:
    session = _FakeSession()
    repository = _FakeUserRepository(users, **kwargs)
    return UserService(session=session, users=repository), session  # type: ignore[arg-type]


def test_list_users_paginates_and_reports_total() -> None:
    users = [_make_user() for _ in range(3)]
    service, _ = _service(users)

    items, total = asyncio.run(service.list_users(UserListFilters(page=1, page_size=2)))

    assert total == 3
    assert len(items) == 2


def test_get_user_raises_not_found_for_unknown_id() -> None:
    service, _ = _service([])

    with pytest.raises(NotFoundException):
        asyncio.run(service.get_user(uuid.uuid4()))


def test_create_user_defaults_role_to_member() -> None:
    service, session = _service([])

    result = asyncio.run(
        service.create_user(
            UserCreate(name="New User", email="new@example.test", password="secret123")
        )
    )

    assert result.role is UserRole.MEMBER
    assert session.commits == 1


def test_create_user_rejects_blank_name() -> None:
    service, _ = _service([])

    with pytest.raises(ValidationException):
        asyncio.run(
            service.create_user(
                UserCreate(name="   ", email="new@example.test", password="secret123")
            )
        )


def test_create_user_translates_integrity_error_to_conflict() -> None:
    service, _ = _service([], fail_on_create=True)

    with pytest.raises(ConflictException):
        asyncio.run(
            service.create_user(
                UserCreate(
                    name="Duplicate", email="dup@example.test", password="secret123"
                )
            )
        )


def test_update_user_rejects_role_change_from_non_admin_actor() -> None:
    target = _make_user()
    actor = _make_user(role=UserRole.MEMBER)
    service, _ = _service([target])

    with pytest.raises(ForbiddenException):
        asyncio.run(
            service.update_user(actor, target.id, UserUpdate(role=UserRole.ADMIN))
        )


def test_update_user_allows_self_edit_of_name() -> None:
    target = _make_user()
    service, session = _service([target])

    result = asyncio.run(
        service.update_user(target, target.id, UserUpdate(name="Renamed  User"))
    )

    assert result.name == normalize_name("Renamed  User")
    assert session.commits == 1


def test_last_admin_guard_blocks_demotion() -> None:
    admin = _make_user(role=UserRole.ADMIN)
    service, _ = _service([admin])

    with pytest.raises(ValidationException):
        asyncio.run(
            service.update_user(admin, admin.id, UserUpdate(role=UserRole.MEMBER))
        )


def test_demotion_succeeds_when_another_admin_remains() -> None:
    admin = _make_user(role=UserRole.ADMIN)
    other_admin = _make_user(role=UserRole.ADMIN)
    service, _ = _service([admin, other_admin])

    result = asyncio.run(
        service.update_user(admin, admin.id, UserUpdate(role=UserRole.MEMBER))
    )

    assert result.role is UserRole.MEMBER


def test_last_admin_guard_blocks_disable() -> None:
    admin = _make_user(role=UserRole.ADMIN)
    service, _ = _service([admin])

    with pytest.raises(ValidationException):
        asyncio.run(service.disable_user(admin.id))


def test_disable_succeeds_when_another_admin_remains() -> None:
    admin = _make_user(role=UserRole.ADMIN)
    other_admin = _make_user(role=UserRole.ADMIN)
    service, session = _service([admin, other_admin])

    result = asyncio.run(service.disable_user(admin.id))

    assert result.disabled_at is not None
    assert session.commits == 1
