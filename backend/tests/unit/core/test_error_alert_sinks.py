from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging

import httpx
from pydantic import SecretStr
import pytest

from app.core.error_alert_sinks import (
    AlertNotification,
    LoggingErrorAlertSink,
    WebhookErrorAlertSink,
    build_error_alert_sink,
)

WEBHOOK_URL = "https://hooks.example.test/services/T000/B000/secret-part"
OCCURRED_AT = datetime(2026, 10, 28, 17, 32, 7, tzinfo=UTC)


def _notification(
    code: str | None = "app/x.py:1 in f\n    raise X",
) -> AlertNotification:
    return AlertNotification(
        severity="error",
        title="KeyError in GET /items/{item_id}",
        environment="production",
        occurred_at=OCCURRED_AT,
        fields=(("Route", "/items/{item_id}"), ("Release", "r1")),
        code=code,
    )


class RecordingTransport(httpx.AsyncBaseTransport):
    """Answer every request with a fixed status and keep what was sent."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status_code, text="ok")


class TimingOutTransport(httpx.AsyncBaseTransport):
    """Fail every request with a read timeout."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)


def test_text_rendering_lists_fields_and_fences_the_traceback_last() -> None:
    text = _notification().as_text()

    lines = text.splitlines()
    assert lines[0] == "[ERROR] KeyError in GET /items/{item_id}"
    assert "Route: /items/{item_id}" in lines
    assert "Release: r1" in lines
    assert text.endswith("    raise X```")


def test_a_code_fence_inside_the_traceback_cannot_close_the_block() -> None:
    text = _notification(code="before ``` after").as_text()

    assert text.count("```") == 2
    assert "before ''' after" in text


def test_webhook_sink_posts_a_slack_compatible_text_body() -> None:
    transport = RecordingTransport()
    sink = WebhookErrorAlertSink(url=SecretStr(WEBHOOK_URL), transport=transport)

    asyncio.run(sink.deliver(_notification()))

    [request] = transport.requests
    assert request.method == "POST"
    assert str(request.url) == WEBHOOK_URL
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {"text": _notification().as_text()}


@pytest.mark.parametrize(
    ("transport", "reason"),
    [(TimingOutTransport(), "ReadTimeout"), (RecordingTransport(500), "http_500")],
)
def test_webhook_failure_logs_one_warning_without_the_url(
    transport: httpx.AsyncBaseTransport,
    reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    sink = WebhookErrorAlertSink(url=SecretStr(WEBHOOK_URL), transport=transport)

    asyncio.run(sink.deliver(_notification()))

    [record] = [
        r for r in caplog.records if r.getMessage() == "error alert not delivered"
    ]
    assert record.error_type == reason
    assert "secret-part" not in caplog.text


def test_logging_sink_writes_one_record_at_the_notification_severity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    asyncio.run(LoggingErrorAlertSink().deliver(_notification()))

    [record] = [r for r in caplog.records if r.getMessage().startswith("error alert:")]
    assert record.levelno == logging.ERROR
    assert record.alert_fields == {"Route": "/items/{item_id}", "Release": "r1"}


def test_build_selects_the_sink_from_the_url() -> None:
    assert isinstance(build_error_alert_sink(SecretStr("")), LoggingErrorAlertSink)
    assert isinstance(build_error_alert_sink(SecretStr("  ")), LoggingErrorAlertSink)
    assert isinstance(
        build_error_alert_sink(SecretStr(WEBHOOK_URL)), WebhookErrorAlertSink
    )


def test_build_refuses_a_url_that_is_not_http() -> None:
    with pytest.raises(ValueError, match="http"):
        build_error_alert_sink(SecretStr("ftp://hooks.example.test/x"))
