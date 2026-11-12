"""Unhandled errors leave the 500 unchanged and hand one alert to the sink."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import logging

from fastapi import APIRouter
from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest

from app.config import Settings
from app.core import REQUEST_ID_HEADER, NotFoundException
from app.core.error_alert_reporter import build_error_alert_reporter
from app.core.error_alert_sinks import ErrorAlertSink, WebhookErrorAlertSink
from app.main import app
from tests.support.error_alert_fakes import RecordingErrorAlertSink

RELEASE = "abc12345"
ROUTE_TEMPLATE = "/__test/error-alerts/items/{item_id}"
INTERNAL_ERROR = {"code": "internal_error", "message": "An internal error occurred"}
LEAKED_EMAIL = "jane.doe@example.org"

InstallReporter = Callable[[str, ErrorAlertSink], None]

alerts_router = APIRouter(prefix="/error-alerts")


@alerts_router.get("/items/{item_id}")
async def failing_endpoint(item_id: str) -> dict[str, str]:
    lookup: dict[str, str] = {}
    try:
        return {"value": lookup[item_id]}
    except KeyError:
        raise RuntimeError(f"lookup failed for {LEAKED_EMAIL}") from None


@alerts_router.get("/missing")
async def missing_endpoint() -> None:
    raise NotFoundException()


app.include_router(alerts_router, prefix="/__test")


class TimingOutTransport(httpx.AsyncBaseTransport):
    """Fail every webhook request with a read timeout."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)


def _settings(environment: str) -> Settings:
    return Settings(
        TESTING=True,
        ENVIRONMENT=environment,  # type: ignore[arg-type]
        APP_VERSION=RELEASE,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def install_reporter() -> Iterator[InstallReporter]:
    previous = app.state.error_alerts

    def install(environment: str, sink: ErrorAlertSink) -> None:
        app.state.error_alerts = build_error_alert_reporter(
            _settings(environment), sink
        )

    yield install
    app.state.error_alerts = previous


def _assert_internal_error(response: httpx.Response) -> str:
    assert response.status_code == 500
    body = response.json()
    request_id = body.pop("request_id")
    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert body == {"error": INTERNAL_ERROR}
    return str(request_id)


def test_unhandled_error_delivers_one_scrubbed_alert_in_production(
    error_client: TestClient, install_reporter: InstallReporter
) -> None:
    sink = RecordingErrorAlertSink()
    install_reporter("production", sink)

    response = error_client.get("/__test/error-alerts/items/42")

    request_id = _assert_internal_error(response)
    [alert] = sink.delivered
    fields = dict(alert.fields)
    assert alert.severity == "error"
    assert alert.title == f"RuntimeError in GET {ROUTE_TEMPLATE}"
    assert fields["Route"] == ROUTE_TEMPLATE
    assert fields["Request id"] == request_id
    assert fields["Release"] == RELEASE
    assert fields["Message"] == "lookup failed for [email]"
    assert fields["Failure site"].startswith("app/")
    assert alert.code is not None and "raise RuntimeError" in alert.code
    assert "/items/42" not in alert.as_text()
    assert LEAKED_EMAIL not in alert.as_text()


def test_repeated_errors_deliver_only_the_first_alert(
    error_client: TestClient, install_reporter: InstallReporter
) -> None:
    sink = RecordingErrorAlertSink()
    install_reporter("production", sink)

    for item in ("1", "2", "3"):
        _assert_internal_error(error_client.get(f"/__test/error-alerts/items/{item}"))

    assert len(sink.delivered) == 1


def test_api_exception_delivers_nothing(
    error_client: TestClient, install_reporter: InstallReporter
) -> None:
    sink = RecordingErrorAlertSink()
    install_reporter("production", sink)

    response = error_client.get("/__test/error-alerts/missing")

    assert response.status_code == 404
    assert sink.delivered == []


def test_unhandled_error_delivers_nothing_in_development(
    error_client: TestClient, install_reporter: InstallReporter
) -> None:
    sink = RecordingErrorAlertSink()
    install_reporter("development", sink)

    _assert_internal_error(error_client.get("/__test/error-alerts/items/42"))

    assert sink.delivered == []


def test_webhook_timeout_leaves_the_500_unchanged_and_logs_one_warning(
    error_client: TestClient,
    install_reporter: InstallReporter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    sink = WebhookErrorAlertSink(
        url=SecretStr("https://hooks.example.test/services/T000/B000/secret-part"),
        transport=TimingOutTransport(),
    )
    install_reporter("production", sink)

    _assert_internal_error(error_client.get("/__test/error-alerts/items/42"))

    warnings = [
        record
        for record in caplog.records
        if record.getMessage() == "error alert not delivered"
    ]
    assert len(warnings) == 1
    assert "secret-part" not in caplog.text
