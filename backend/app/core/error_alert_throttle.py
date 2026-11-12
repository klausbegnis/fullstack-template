"""Bound error alert posts per process: dedupe repeats and cap the hourly rate.

The throttle is pure: every call takes the current time, so a test drives it
with a fake clock. The first occurrence of a fingerprint posts when the hourly
cap allows; repeats inside its window are only counted, and one summary with
the count is due when the window closes. A post past the cap is dropped and
counted; one notice with that count is due when the hour turns, and the notice
itself is never capped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.error_alerts import ErrorAlert

HOUR = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class RepeatSummary:
    """Repeats of `alert`'s failure counted while its window was open."""

    alert: ErrorAlert
    count: int


@dataclass(frozen=True, slots=True)
class SuppressedNotice:
    """Posts dropped because the hourly cap was reached."""

    count: int


ThrottleEvent = RepeatSummary | SuppressedNotice


@dataclass(slots=True)
class _Window:
    alert: ErrorAlert
    closes_at: datetime
    repeats: int = 0


class AlertThrottle:
    """Per-process dedupe window and hourly cap for error alerts."""

    def __init__(self, *, window: timedelta, max_posts_per_hour: int) -> None:
        self._window = window
        self._max_posts_per_hour = max_posts_per_hour
        self._windows: dict[str, _Window] = {}
        self._closed: list[_Window] = []
        self._hour_started_at: datetime | None = None
        self._posts_this_hour = 0
        self._suppressed_this_hour = 0
        self._suppressed_unreported = 0
        self._last_seen_at: datetime | None = None

    def admit(self, alert: ErrorAlert, now: datetime) -> bool:
        """Return whether `alert` posts now; otherwise it is counted."""
        self._advance(now)
        window = self._windows.get(alert.fingerprint)
        if window is not None:
            window.repeats += 1
            return False
        if not self._take_slot():
            return False
        self._windows[alert.fingerprint] = _Window(alert, now + self._window)
        return True

    def due(self, now: datetime) -> list[ThrottleEvent]:
        """Return the summaries and the suppressed notice that are due by `now`."""
        self._advance(now)
        events: list[ThrottleEvent] = []
        for window in self._closed:
            if self._take_slot():
                events.append(RepeatSummary(window.alert, window.repeats))
        self._closed.clear()
        if self._suppressed_unreported:
            events.append(SuppressedNotice(self._suppressed_unreported))
            self._suppressed_unreported = 0
        return events

    def next_deadline(self) -> datetime | None:
        """Return when the next summary or notice falls due, if one is pending."""
        deadlines = [
            window.closes_at for window in self._windows.values() if window.repeats
        ]
        if self._closed or self._suppressed_unreported:
            return self._last_seen_at
        if self._suppressed_this_hour and self._hour_started_at is not None:
            deadlines.append(self._hour_started_at + HOUR)
        return min(deadlines, default=None)

    def _advance(self, now: datetime) -> None:
        self._last_seen_at = now
        self._roll_hour(now)
        for fingerprint, window in list(self._windows.items()):
            if now >= window.closes_at:
                del self._windows[fingerprint]
                if window.repeats:
                    self._closed.append(window)

    def _roll_hour(self, now: datetime) -> None:
        if self._hour_started_at is not None and now < self._hour_started_at + HOUR:
            return
        self._suppressed_unreported += self._suppressed_this_hour
        self._hour_started_at = now
        self._posts_this_hour = 0
        self._suppressed_this_hour = 0

    def _take_slot(self) -> bool:
        if self._posts_this_hour >= self._max_posts_per_hour:
            self._suppressed_this_hour += 1
            return False
        self._posts_this_hour += 1
        return True
