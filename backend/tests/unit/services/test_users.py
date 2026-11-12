from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.user import User, UserRole
from app.schemas.api.users import UserCreate, UserListFilters, UserUpdate
from app.services.users import UserService, normalize_name
from tests.support.fakes import (
    FakeSecurityEventRepository,
    FakeSession,
    FakeUserRepository,
    make_user,
)

ADMIN = make_user(role=UserRole.ADMIN)


def _service(users: list[User], **kwargs: bool) -> tuple[UserService, FakeSession]:
    service, session, _ = _audited_service(users, **kwargs)
    return service, session


def _audited_service(
    users: list[User], **kwargs: bool
) -> tuple[UserService, FakeSession, FakeSecurityEventRepository]:
    session = FakeSession()
    events = FakeSecurityEventRepository()
    service = UserService(
        session=session,  # type: ignore[arg-type]
        users=FakeUserRepository(users, **kwargs),  # type: ignore[arg-type]
        security_events=events,  # type: ignore[arg-type]
    )
    return service, session, events


def test_list_users_paginates_and_reports_total() -> None:
    users = [make_user() for _ in range(3)]
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
            ADMIN,
            UserCreate(name="New User", email="new@example.test", password="secret123"),
        )
    )

    assert result.role is UserRole.MEMBER
    assert session.commits == 1


def test_create_user_rejects_blank_name() -> None:
    service, _ = _service([])

    with pytest.raises(ValidationException):
        asyncio.run(
            service.create_user(
                ADMIN,
                UserCreate(name="   ", email="new@example.test", password="secret123"),
            )
        )


def test_create_user_translates_integrity_error_to_conflict() -> None:
    service, _ = _service([], fail_on_create=True)

    with pytest.raises(ConflictException):
        asyncio.run(
            service.create_user(
                ADMIN,
                UserCreate(
                    name="Duplicate", email="dup@example.test", password="secret123"
                ),
            )
        )


def test_update_user_rejects_role_change_from_non_admin_actor() -> None:
    target = make_user()
    actor = make_user(role=UserRole.MEMBER)
    service, _ = _service([target])

    with pytest.raises(ForbiddenException):
        asyncio.run(
            service.update_user(actor, target.id, UserUpdate(role=UserRole.ADMIN))
        )


def test_update_user_allows_self_edit_of_name() -> None:
    target = make_user()
    service, session = _service([target])

    result = asyncio.run(
        service.update_user(target, target.id, UserUpdate(name="Renamed  User"))
    )

    assert result.name == normalize_name("Renamed  User")
    assert session.commits == 1


def test_last_admin_guard_blocks_demotion() -> None:
    admin = make_user(role=UserRole.ADMIN)
    service, _ = _service([admin])

    with pytest.raises(ValidationException):
        asyncio.run(
            service.update_user(admin, admin.id, UserUpdate(role=UserRole.MEMBER))
        )


def test_demotion_succeeds_when_another_admin_remains() -> None:
    admin = make_user(role=UserRole.ADMIN)
    other_admin = make_user(role=UserRole.ADMIN)
    service, _ = _service([admin, other_admin])

    result = asyncio.run(
        service.update_user(admin, admin.id, UserUpdate(role=UserRole.MEMBER))
    )

    assert result.role is UserRole.MEMBER


def test_last_admin_guard_blocks_disable() -> None:
    admin = make_user(role=UserRole.ADMIN)
    service, _ = _service([admin])

    with pytest.raises(ValidationException):
        asyncio.run(service.disable_user(admin, admin.id))


def test_disable_succeeds_when_another_admin_remains() -> None:
    admin = make_user(role=UserRole.ADMIN)
    other_admin = make_user(role=UserRole.ADMIN)
    service, session = _service([admin, other_admin])

    result = asyncio.run(service.disable_user(other_admin, admin.id))

    assert result.disabled_at is not None
    assert session.commits == 1


def test_create_user_records_the_admin_as_actor() -> None:
    service, _, events = _audited_service([])

    result = asyncio.run(
        service.create_user(
            ADMIN,
            UserCreate(
                name="New User",
                email="new@example.test",
                password="secret123",
                role=UserRole.ADMIN,
            ),
        )
    )

    [event] = events.events
    assert (event.action, event.user_id, event.actor_user_id) == (
        "user.created",
        result.id,
        ADMIN.id,
    )
    assert event.payload == {"role": "admin"}


def test_update_user_records_changed_fields_without_their_values() -> None:
    target = make_user()
    service, _, events = _audited_service([target])

    asyncio.run(
        service.update_user(
            ADMIN,
            target.id,
            UserUpdate(name="Renamed User", email="renamed@example.test"),
        )
    )

    [event] = events.events
    assert event.action == "user.updated"
    assert event.payload == {"fields": ["email", "name"]}
    assert "renamed" not in repr(event.payload)


def test_role_change_records_old_and_new_role() -> None:
    target = make_user()
    service, _, events = _audited_service([target, ADMIN])

    asyncio.run(service.update_user(ADMIN, target.id, UserUpdate(role=UserRole.ADMIN)))

    assert events.actions == ["user.role_changed"]
    assert events.events[0].payload == {"old_role": "member", "role": "admin"}
    assert events.events[0].actor_user_id == ADMIN.id


def test_setting_the_same_role_records_nothing() -> None:
    target = make_user()
    service, _, events = _audited_service([target])

    asyncio.run(service.update_user(ADMIN, target.id, UserUpdate(role=UserRole.MEMBER)))

    assert events.events == []


def test_disable_records_the_admin_as_actor() -> None:
    target = make_user()
    service, session, events = _audited_service([target])

    asyncio.run(service.disable_user(ADMIN, target.id))

    [event] = events.events
    assert (event.action, event.user_id, event.actor_user_id) == (
        "user.disabled",
        target.id,
        ADMIN.id,
    )
    assert session.commits == 1


def test_a_refused_disable_records_nothing() -> None:
    admin = make_user(role=UserRole.ADMIN)
    service, _, events = _audited_service([admin])

    with pytest.raises(ValidationException):
        asyncio.run(service.disable_user(admin, admin.id))

    assert events.events == []
