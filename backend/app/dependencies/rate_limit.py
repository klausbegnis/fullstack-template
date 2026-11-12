"""Rate-limit dependencies a router declares per scope, e.g. `rate_limited("login")`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import json
from typing import Annotated, Any, Protocol

from fastapi import Depends, Request

from app.config import Settings, SettingsDep
from app.core.clock import Clock
from app.core.database import SessionFactory, request_session_factory
from app.core.exceptions import TooManyRequestsException
from app.core.rate_limit import client_ip, ensure_known_scope, policy_for
from app.repositories.rate_limit_windows import RateLimitWindowRepository
from app.repositories.users import normalize_email
from app.services.rate_limits import RateLimitService, digest_key

from .clock import ClockDep

MAX_EMAIL_LENGTH = 320


class RateLimitCounter(Protocol):
    """Count one hit of `(scope, subject)` and report the wait once over `limit`."""

    async def hit(
        self, scope: str, subject: str, *, limit: int, window_seconds: int
    ) -> int | None: ...


class SharedWindowCounter:
    """Count each hit on a session of its own, committed before the route runs.

    The route's request session rolls back when the route fails, so a hit made
    on it would be lost with a failed login; this counter's session is opened
    and closed around every hit instead. `sessions` is resolved at each hit,
    so a disabled limiter needs no database.
    """

    def __init__(
        self, sessions: Callable[[], SessionFactory], clock: Clock, key: bytes
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._key = key

    async def hit(
        self, scope: str, subject: str, *, limit: int, window_seconds: int
    ) -> int | None:
        async with self._sessions()() as session:
            service = RateLimitService(
                session=session,
                windows=RateLimitWindowRepository(session),
                clock=self._clock,
                key=self._key,
            )
            return await service.hit(
                scope, subject, limit=limit, window_seconds=window_seconds
            )


def get_rate_limit_counter(
    request: Request, clock: ClockDep, config: SettingsDep
) -> RateLimitCounter:
    """Return the counter backed by the shared `iam.rate_limit_windows` table."""
    return SharedWindowCounter(
        lambda: request_session_factory(request),
        clock,
        digest_key(config.AUTH_JWT_SECRET.get_secret_value()),
    )


RateLimitCounterDep = Annotated[RateLimitCounter, Depends(get_rate_limit_counter)]
SubjectExtractor = Callable[[Request, Settings], Awaitable[str | None]]


async def _body_field(request: Request, field: str) -> str | None:
    try:
        body: Any = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    value = body.get(field) if isinstance(body, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value


async def email_subject(request: Request, config: Settings) -> str | None:
    """Key on the normalized body `email`; an over-long email is not a subject."""
    del config
    email = await _body_field(request, "email")
    if email is None:
        return None
    normalized = normalize_email(email)
    if len(normalized) > MAX_EMAIL_LENGTH:
        return None
    return normalized


def rate_limited(
    scope: str, subject: SubjectExtractor = email_subject
) -> Callable[..., Awaitable[None]]:
    """Build a dependency counting every request of `scope` per subject and per IP.

    The subject defaults to the request's normalized email. Every attempt
    counts, whether it later succeeds or fails, and no window is reset on
    success. A request without a usable subject is still counted per IP. An
    unknown `scope` raises `ValueError` here, at construction, so a mis-wired
    route fails at import time.
    """
    ensure_known_scope(scope)

    async def enforce_rate_limit(
        request: Request, config: SettingsDep, counter: RateLimitCounterDep
    ) -> None:
        if not config.RATE_LIMIT_ENABLED:
            return
        policy = policy_for(scope, config)
        ip = client_ip(
            request,
            trust_forwarded=config.RATE_LIMIT_TRUST_FORWARDED,
            client_ip_header=config.RATE_LIMIT_CLIENT_IP_HEADER,
        )
        retry_after = [
            await counter.hit(
                f"{scope}:ip",
                ip,
                limit=policy.per_ip,
                window_seconds=policy.window_seconds,
            )
        ]
        key = await subject(request, config)
        if key is not None:
            retry_after.append(
                await counter.hit(
                    f"{scope}:subject",
                    key,
                    limit=policy.per_subject,
                    window_seconds=policy.window_seconds,
                )
            )
        exceeded = [seconds for seconds in retry_after if seconds is not None]
        if exceeded:
            raise TooManyRequestsException(retry_after_seconds=max(exceeded))

    return enforce_rate_limit


__all__ = [
    "MAX_EMAIL_LENGTH",
    "RateLimitCounter",
    "RateLimitCounterDep",
    "SharedWindowCounter",
    "email_subject",
    "get_rate_limit_counter",
    "rate_limited",
]
