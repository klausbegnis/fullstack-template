from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.core.error_alert_reporter import (
    ErrorAlertReporter,
    build_error_alert_reporter,
)
from app.core.error_alert_sinks import LoggingErrorAlertSink, WebhookErrorAlertSink
from app.core.error_alert_throttle import AlertThrottle
from app.core.error_alerts import ErrorAlert
from tests.support.error_alert_fakes import RecordingErrorAlertSink

START = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=10)


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _alert(route: str = "/items/{item_id}") -> ErrorAlert:
    return ErrorAlert(
        exception_class="KeyError",
        method="GET",
        route_template=route,
        request_id="req-1",
        user_id=None,
        failure_site="app/services/items.py:10 in load",
        message="'missing'",
        traceback="app/services/items.py:10 in load",
        occurred_at=START,
    )


def _reporter(sink: RecordingErrorAlertSink, clock: FakeClock) -> ErrorAlertReporter:
    return ErrorAlertReporter(
        sink=sink,
        throttle=AlertThrottle(window=WINDOW, max_posts_per_hour=20),
        environment="production",
        release="abc12345",
        enabled=True,
        clock=clock,
    )


def test_identical_errors_in_one_window_deliver_first_and_one_summary() -> None:
    sink = RecordingErrorAlertSink()
    clock = FakeClock(START)

    async def scenario() -> None:
        reporter = _reporter(sink, clock)
        for second in range(400):
            clock.now = START + timedelta(seconds=second)
            await reporter.report(_alert())
        clock.now = START + WINDOW
        await reporter.flush()
        await reporter.aclose()

    asyncio.run(scenario())

    first, summary = sink.delivered
    assert first.severity == "error"
    assert first.title == "KeyError in GET /items/{item_id}"
    assert summary.severity == "warning"
    assert summary.title.startswith("399x ")


def test_distinct_errors_past_the_hourly_cap_deliver_one_suppressed_notice() -> None:
    sink = RecordingErrorAlertSink()
    clock = FakeClock(START)

    async def scenario() -> None:
        reporter = _reporter(sink, clock)
        for index in range(30):
            clock.now = START + timedelta(minutes=index)
            await reporter.report(_alert(f"/route-{index}"))
        clock.now = START + timedelta(hours=1)
        await reporter.flush()
        await reporter.aclose()

    asyncio.run(scenario())

    severities = [notification.severity for notification in sink.delivered]
    assert severities == ["error"] * 20 + ["warning"]
    assert sink.delivered[-1].title == "10 error alerts suppressed"


def test_pending_summary_is_due_when_the_window_closes() -> None:
    throttle = AlertThrottle(window=WINDOW, max_posts_per_hour=20)

    assert throttle.admit(_alert(), START)
    assert not throttle.admit(_alert(), START + timedelta(seconds=1))

    assert throttle.next_deadline() == START + WINDOW
    assert throttle.due(START + WINDOW - timedelta(seconds=1)) == []


def test_aclose_cancels_and_awaits_the_pending_flush_task() -> None:
    sink = RecordingErrorAlertSink()
    clock = FakeClock(START)

    async def scenario() -> asyncio.Task[None] | None:
        reporter = _reporter(sink, clock)
        await reporter.report(_alert())
        await reporter.report(_alert())
        pending = reporter._flush_task
        assert pending is not None and not pending.done()
        await reporter.aclose()
        assert reporter._flush_task is None
        return pending

    pending = asyncio.run(scenario())

    assert pending is not None
    assert pending.cancelled()
    assert len(sink.delivered) == 1


class FailingSink:
    """A sink whose delivery always raises."""

    async def deliver(self, notification: object) -> None:
        raise RuntimeError("sink down")


def test_a_failing_sink_never_raises_out_of_report() -> None:
    reporter = ErrorAlertReporter(
        sink=FailingSink(),  # type: ignore[arg-type]
        throttle=AlertThrottle(window=WINDOW, max_posts_per_hour=20),
        environment="production",
        release="r1",
        enabled=True,
        clock=FakeClock(START),
    )

    asyncio.run(reporter.report(_alert()))


def _settings(**overrides: object) -> Settings:
    return Settings(TESTING=True, **overrides)  # type: ignore[arg-type]


def test_reporter_is_enabled_only_in_production() -> None:
    assert build_error_alert_reporter(_settings(ENVIRONMENT="production")).enabled
    assert not build_error_alert_reporter(_settings(ENVIRONMENT="development")).enabled


def test_default_sink_logs_and_a_webhook_url_selects_the_webhook_sink() -> None:
    logging_reporter = build_error_alert_reporter(_settings())
    webhook_reporter = build_error_alert_reporter(
        _settings(ERROR_ALERT_WEBHOOK_URL="https://hooks.example.test/T000/B000/x")
    )

    assert isinstance(logging_reporter._sink, LoggingErrorAlertSink)
    assert isinstance(webhook_reporter._sink, WebhookErrorAlertSink)
