"""Record account security events in `iam.security_events` and the log.

Every event is one append-only row about one user plus one log line carrying
only the action and the user's id. No email, password, token or other secret is
ever recorded: a payload key that looks like one is refused outright.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Protocol
import uuid

from app.core.logger import get_logger
from app.models.security_event import SecurityEvent

logger = get_logger(__name__)

LOGIN_SUCCEEDED = "auth.login_succeeded"
LOGIN_FAILED = "auth.login_failed"
LOGOUT = "auth.logout"
REFRESH_TOKEN_REUSED = "auth.refresh_token_reused"  # noqa: S105
USER_CREATED = "user.created"
USER_UPDATED = "user.updated"
ROLE_CHANGED = "user.role_changed"
USER_DISABLED = "user.disabled"

SENSITIVE_KEY = re.compile(
    r"password|secret|token|credential|authorization|cookie|email",
    re.IGNORECASE,
)


class SecurityEventStore(Protocol):
    """The persistence `record_security_event` appends through."""

    async def append(
        self,
        *,
        action: str,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        payload: dict[str, object],
    ) -> SecurityEvent: ...


def safe_payload(value: Mapping[str, object]) -> dict[str, object]:
    """Return a JSON-safe copy of `value`, refusing keys that name a secret.

    A refused payload is a programming error, so it raises `ValueError`
    rather than a client-facing exception.
    """
    safe: dict[str, object] = {}
    for key, item in value.items():
        if SENSITIVE_KEY.search(key):
            raise ValueError(f"Security event payload key {key!r} names a secret")
        safe[key] = _safe_value(item)
    return safe


def _safe_value(value: object) -> object:
    if isinstance(value, Mapping):
        return safe_payload(value)
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Security event payload must hold JSON-compatible values")


async def record_security_event(
    events: SecurityEventStore,
    *,
    action: str,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    payload: Mapping[str, object] | None = None,
) -> None:
    """Append one screened event about `user_id` inside the caller's transaction."""
    await events.append(
        action=action,
        user_id=user_id,
        actor_user_id=actor_user_id,
        payload=safe_payload(payload or {}),
    )
    logger.info(
        "security event recorded", extra={"action": action, "user_id": str(user_id)}
    )


__all__ = [
    "LOGIN_FAILED",
    "LOGIN_SUCCEEDED",
    "LOGOUT",
    "REFRESH_TOKEN_REUSED",
    "ROLE_CHANGED",
    "USER_CREATED",
    "USER_DISABLED",
    "USER_UPDATED",
    "SecurityEventStore",
    "record_security_event",
    "safe_payload",
]
