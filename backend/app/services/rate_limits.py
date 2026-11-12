"""Count rate-limited attempts in the windows every worker shares.

Each hit commits in its own short transaction, so an attempt still counts when
the request that made it later fails.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import math
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.transactions import transaction
from app.repositories.rate_limit_windows import WindowCount


class RateLimitWindowStore(Protocol):
    """The window persistence `RateLimitService` counts through."""

    async def hit(
        self,
        scope: str,
        subject_digest: bytes,
        *,
        now: datetime,
        window: timedelta,
    ) -> WindowCount: ...

    async def count_expired(self, *, before: datetime, limit: int) -> int: ...

    async def delete_expired(self, *, before: datetime, limit: int) -> int: ...


DIGEST_KEY_CONTEXT = b"rate-limit-subject:"


def digest_key(secret: str) -> bytes:
    """Derive the HMAC key for subject digests from a server secret."""
    return hashlib.sha256(DIGEST_KEY_CONTEXT + secret.encode()).digest()


def subject_digest(subject: str, key: bytes) -> bytes:
    """Return the 32-byte HMAC-SHA256 stored in place of the plain subject.

    Keyed with a server secret, so a read of the table cannot recover an email
    or an IPv4 address by hashing candidates.
    """
    return hmac.new(key, subject.encode(), hashlib.sha256).digest()


class RateLimitService:
    """Count hits per scope and subject, and purge windows that have ended."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        windows: RateLimitWindowStore,
        clock: Clock,
        key: bytes,
    ) -> None:
        self._session = session
        self._windows = windows
        self._clock = clock
        self._key = key

    async def hit(
        self, scope: str, subject: str, *, limit: int, window_seconds: int
    ) -> int | None:
        """Count one hit; return seconds until the window resets once over the limit."""
        now = self._clock()
        async with transaction(self._session):
            count = await self._windows.hit(
                scope,
                subject_digest(subject, self._key),
                now=now,
                window=timedelta(seconds=window_seconds),
            )
        if count.hits <= limit:
            return None
        return max(1, math.ceil((count.resets_at - now).total_seconds()))

    async def purge_expired(self, *, limit: int, dry_run: bool) -> int:
        """Delete up to `limit` ended windows, or only count them on a dry run."""
        before = self._clock()
        async with transaction(self._session):
            if dry_run:
                return await self._windows.count_expired(before=before, limit=limit)
            return await self._windows.delete_expired(before=before, limit=limit)


__all__ = [
    "RateLimitService",
    "RateLimitWindowStore",
    "digest_key",
    "subject_digest",
]
