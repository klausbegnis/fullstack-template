"""The wall clock as an injectable callable, so tests can move time by hand."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return the current time, timezone-aware in UTC."""
    return datetime.now(UTC)


__all__ = ["Clock", "utc_now"]
