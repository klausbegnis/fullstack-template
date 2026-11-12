from __future__ import annotations

import asyncio
import logging
import uuid

import pytest

from app.services.security_audit import (
    LOGIN_FAILED,
    record_security_event,
    safe_payload,
)
from tests.support.fakes import FakeSecurityEventRepository


def test_record_security_event_appends_one_row_and_logs_only_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    events = FakeSecurityEventRepository()
    user_id, actor_id = uuid.uuid4(), uuid.uuid4()
    caplog.set_level(logging.INFO)

    asyncio.run(
        record_security_event(
            events,
            action=LOGIN_FAILED,
            user_id=user_id,
            actor_user_id=actor_id,
            payload={"reason": "invalid_password"},
        )
    )

    [event] = events.events
    assert event.user_id == user_id
    assert event.actor_user_id == actor_id
    assert event.action == "auth.login_failed"
    assert event.payload == {"reason": "invalid_password"}
    [record] = [
        r for r in caplog.records if r.getMessage() == "security event recorded"
    ]
    assert record.action == "auth.login_failed"
    assert record.user_id == str(user_id)


def test_record_security_event_defaults_to_an_empty_payload() -> None:
    events = FakeSecurityEventRepository()

    asyncio.run(
        record_security_event(
            events, action=LOGIN_FAILED, user_id=uuid.uuid4(), actor_user_id=None
        )
    )

    assert events.events[0].payload == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "hunter2"},
        {"nested": {"refresh_token": "abc"}},
        {"items": [{"Email": "someone@example.test"}]},
    ],
)
def test_record_security_event_refuses_a_sensitive_payload_key(
    payload: dict[str, object],
) -> None:
    events = FakeSecurityEventRepository()

    with pytest.raises(ValueError, match="names a secret"):
        asyncio.run(
            record_security_event(
                events,
                action=LOGIN_FAILED,
                user_id=uuid.uuid4(),
                actor_user_id=None,
                payload=payload,
            )
        )

    assert events.events == []


def test_safe_payload_refuses_a_value_that_is_not_json() -> None:
    with pytest.raises(ValueError, match="JSON-compatible"):
        safe_payload({"at": object()})


def test_safe_payload_copies_nested_json_values() -> None:
    assert safe_payload({"fields": ("name", "email"), "count": 2}) == {
        "fields": ["name", "email"],
        "count": 2,
    }
