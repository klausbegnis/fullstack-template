"""Deliver unhandled-exception alerts to a pluggable sink, deduplicated and capped.

One reporter lives per process on `app.state.error_alerts`, composed in
`main.py`. The exception handler runs `report` as the 500 response's background
task, so delivery happens after the body is sent and never changes it. A
summary or notice that falls due later is delivered by one pending flush task.
Reporting never raises: a failure becomes one warning.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta

from app.config import Settings
from app.core.clock import Clock, utc_now
from app.core.error_alert_sinks import (
    AlertNotification,
    ErrorAlertSink,
    build_error_alert_sink,
    error_alert_notification,
    repeat_summary_notification,
    suppressed_notification,
)
from app.core.error_alert_throttle import AlertThrottle, RepeatSummary, ThrottleEvent
from app.core.error_alerts import ErrorAlert
from app.core.logger import get_logger

logger = get_logger(__name__)

PRODUCTION = "production"


class ErrorAlertReporter:
    """Turn captured alerts into throttled notifications for one sink."""

    def __init__(
        self,
        *,
        sink: ErrorAlertSink,
        throttle: AlertThrottle,
        environment: str,
        release: str,
        enabled: bool,
        clock: Clock,
    ) -> None:
        self._sink = sink
        self._throttle = throttle
        self._environment = environment
        self._release = release
        self._enabled = enabled
        self._clock = clock
        self._flush_task: asyncio.Task[None] | None = None
        self._flush_at: datetime | None = None

    @property
    def enabled(self) -> bool:
        """Whether this process reports unhandled exceptions at all."""
        return self._enabled

    def now(self) -> datetime:
        """Return the reporter's current time."""
        return self._clock()

    async def report(self, alert: ErrorAlert) -> None:
        """Deliver `alert` unless it repeats or exceeds the cap; never raise."""
        try:
            now = self._clock()
            notifications = self._due_notifications(now)
            if self._throttle.admit(alert, now):
                notifications.append(
                    error_alert_notification(
                        alert, environment=self._environment, release=self._release
                    )
                )
            await self._deliver_all(notifications)
            self._schedule_flush()
        except Exception as exc:
            _log_failure(exc)

    async def flush(self) -> None:
        """Deliver every summary and notice that is due now; never raise."""
        try:
            await self._deliver_all(self._due_notifications(self._clock()))
        except Exception as exc:
            _log_failure(exc)

    async def aclose(self) -> None:
        """Cancel the pending flush task, if any, and wait for it to stop."""
        task, self._flush_task, self._flush_at = self._flush_task, None, None
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _due_notifications(self, now: datetime) -> list[AlertNotification]:
        return [self._notification(event, now) for event in self._throttle.due(now)]

    def _notification(self, event: ThrottleEvent, now: datetime) -> AlertNotification:
        if isinstance(event, RepeatSummary):
            return repeat_summary_notification(
                event.alert,
                count=event.count,
                environment=self._environment,
                release=self._release,
                occurred_at=now,
            )
        return suppressed_notification(
            count=event.count,
            environment=self._environment,
            release=self._release,
            occurred_at=now,
        )

    async def _deliver_all(self, notifications: list[AlertNotification]) -> None:
        for notification in notifications:
            await self._sink.deliver(notification)

    def _schedule_flush(self) -> None:
        deadline = self._throttle.next_deadline()
        if deadline is None or self._flush_pending_by(deadline):
            return
        if self._flush_task is not None:
            self._flush_task.cancel()
        delay = max((deadline - self._clock()).total_seconds(), 0.0)
        self._flush_at = deadline
        self._flush_task = asyncio.create_task(self._flush_after(delay))

    def _flush_pending_by(self, deadline: datetime) -> bool:
        task = self._flush_task
        if task is None or task.done() or self._flush_at is None:
            return False
        if task.get_loop() is not asyncio.get_running_loop():
            return False
        return self._flush_at <= deadline

    async def _flush_after(self, delay: float) -> None:
        await asyncio.sleep(delay)
        self._flush_task, self._flush_at = None, None
        await self.flush()
        self._schedule_flush()


def _log_failure(exc: Exception) -> None:
    logger.warning("error alert not reported", extra={"error_type": type(exc).__name__})


def build_error_alert_reporter(
    settings: Settings,
    sink: ErrorAlertSink | None = None,
    *,
    clock: Clock = utc_now,
) -> ErrorAlertReporter:
    """Compose the reporter; it reports only under `ENVIRONMENT=production`.

    `sink` defaults to the one `ERROR_ALERT_WEBHOOK_URL` selects: the webhook
    when it is set, the structured log otherwise.
    """
    return ErrorAlertReporter(
        sink=sink or build_error_alert_sink(settings.ERROR_ALERT_WEBHOOK_URL),
        throttle=AlertThrottle(
            window=timedelta(seconds=settings.ERROR_ALERT_REPEAT_WINDOW_SECONDS),
            max_posts_per_hour=settings.ERROR_ALERT_MAX_POSTS_PER_HOUR,
        ),
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        enabled=settings.ENVIRONMENT == PRODUCTION,
        clock=clock,
    )


__all__ = ["ErrorAlertReporter", "build_error_alert_reporter"]
