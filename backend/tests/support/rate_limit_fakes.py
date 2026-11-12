"""In-memory doubles for the rate-limit counter and its window repository.

`InMemoryRateLimitCounter` stands in for `get_rate_limit_counter` in DB-free
tests: fixed windows opened by the first hit, like the shared table, keyed on
the subject's digest so the plain value is never kept. `FakeRateLimitWindowStore`
backs `RateLimitService` in its unit tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import time

from app.repositories.rate_limit_windows import WindowCount
from app.services.rate_limits import digest_key, subject_digest

FAKE_DIGEST_KEY = digest_key("fake-rate-limit-secret")


@dataclass
class _Window:
    resets_at: float
    hits: int


class InMemoryRateLimitCounter:
    """Count hits per `(scope, subject digest)` in this process's memory."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.windows: dict[tuple[str, bytes], _Window] = {}

    @property
    def window_count(self) -> int:
        """Return how many windows are stored, expired or not."""
        return len(self.windows)

    async def hit(
        self, scope: str, subject: str, *, limit: int, window_seconds: int
    ) -> int | None:
        now = self._clock()
        key = (scope, subject_digest(subject, FAKE_DIGEST_KEY))
        window = self.windows.get(key)
        if window is None or window.resets_at <= now:
            window = _Window(resets_at=now + window_seconds, hits=0)
            self.windows[key] = window
        window.hits += 1
        if window.hits <= limit:
            return None
        return max(1, math.ceil(window.resets_at - now))


@dataclass
class StoredWindow:
    """One window row kept by `FakeRateLimitWindowStore`."""

    hits: int
    resets_at: datetime


@dataclass
class FakeRateLimitWindowStore:
    """In-memory `RateLimitWindowStore` recording the digests it was given."""

    windows: dict[tuple[str, bytes], StoredWindow] = field(default_factory=dict)

    async def hit(
        self,
        scope: str,
        subject_digest: bytes,
        *,
        now: datetime,
        window: timedelta,
    ) -> WindowCount:
        key = (scope, subject_digest)
        stored = self.windows.get(key)
        if stored is None or stored.resets_at <= now:
            stored = StoredWindow(hits=0, resets_at=now + window)
            self.windows[key] = stored
        stored.hits += 1
        return WindowCount(hits=stored.hits, resets_at=stored.resets_at)

    def _expired(self, before: datetime, limit: int) -> list[tuple[str, bytes]]:
        ordered = sorted(self.windows.items(), key=lambda item: item[1].resets_at)
        return [key for key, stored in ordered if stored.resets_at <= before][:limit]

    async def count_expired(self, *, before: datetime, limit: int) -> int:
        return len(self._expired(before, limit))

    async def delete_expired(self, *, before: datetime, limit: int) -> int:
        expired = self._expired(before, limit)
        for key in expired:
            del self.windows[key]
        return len(expired)
