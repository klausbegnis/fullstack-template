from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json

from starlette.requests import Request

from app.core.error_alert_sinks import error_alert_notification
from app.core.error_alerts import (
    MESSAGE_MAX_CHARACTERS,
    TRACEBACK_MAX_CHARACTERS,
    TRACEBACK_MAX_FRAMES,
    ErrorAlert,
    capture_error_alert,
    drop_database_detail,
    scrub_exception_message,
)

OCCURRED_AT = datetime(2026, 10, 28, 17, 32, 7, tzinfo=UTC)
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


@dataclass(frozen=True)
class MatchedRoute:
    path: str


def _request(path: str = "/items/42", route: object | None = None) -> Request:
    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "state": {"request_id": "req-1"},
    }
    if route is not None:
        scope["route"] = route
    return Request(scope)


def _raised_through_app() -> BaseException:
    try:
        drop_database_detail(123)  # type: ignore[arg-type]
    except TypeError as exc:
        return exc
    raise AssertionError("drop_database_detail accepted an int")


def _raised_deep(depth: int) -> BaseException:
    def recurse(remaining: int) -> None:
        if remaining == 0:
            raise RuntimeError("deep")
        recurse(remaining - 1)

    try:
        recurse(depth)
    except RuntimeError as exc:
        return exc
    raise AssertionError("recurse did not raise")


def _capture(exc: BaseException, request: Request | None = None) -> ErrorAlert:
    return capture_error_alert(request or _request(), exc, OCCURRED_AT)


def test_scrub_replaces_email_phone_and_jwt() -> None:
    scrubbed = scrub_exception_message(
        f"user jane.doe@example.org phone +1 (555) 98765-4321 token {JWT}"
    )

    assert "jane.doe" not in scrubbed
    assert "98765" not in scrubbed
    assert "eyJ" not in scrubbed
    assert scrubbed == "user [email] phone [phone] token [token]"


def test_scrub_caps_a_long_message_at_300_characters() -> None:
    scrubbed = scrub_exception_message("failure " * 100)

    assert len(scrubbed) == MESSAGE_MAX_CHARACTERS


def test_traceback_holds_only_frame_locations_and_source_lines() -> None:
    alert = _capture(_raised_through_app())

    lines = alert.traceback.splitlines()
    locations = lines[0::2]
    assert all(" in " in line and ":" in line for line in locations)
    assert all(line.startswith("    ") for line in lines[1::2])
    assert "req-1" not in alert.traceback


def test_traceback_keeps_at_most_15_frames_within_2500_characters() -> None:
    alert = _capture(_raised_deep(40))

    locations = [line for line in alert.traceback.splitlines() if " in " in line]
    assert len(locations) <= TRACEBACK_MAX_FRAMES
    assert len(alert.traceback) <= TRACEBACK_MAX_CHARACTERS
    assert alert.traceback.endswith('raise RuntimeError("deep")')


def test_failure_site_is_the_innermost_app_frame() -> None:
    alert = _capture(_raised_through_app())

    assert alert.failure_site.startswith("app/core/error_alerts.py:")
    assert alert.failure_site.endswith(" in drop_database_detail")


def test_route_template_comes_from_the_matched_route_not_the_raw_path() -> None:
    request = _request("/items/42", MatchedRoute("/items/{item_id}"))

    alert = _capture(_raised_through_app(), request)

    assert alert.route_template == "/items/{item_id}"
    assert alert.fingerprint == (f"TypeError|/items/{{item_id}}|{alert.failure_site}")


def _captured_payload(message: str) -> str:
    alert = _capture(RuntimeError(message))
    notification = error_alert_notification(
        alert, environment="production", release="r1"
    )
    return json.dumps({"text": notification.as_text()}, ensure_ascii=False)


def test_sql_and_bound_parameters_never_reach_the_payload() -> None:
    payload = _captured_payload(
        "(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) insert failed "
        "[SQL: INSERT INTO customers (name, address) VALUES ($1, $2)] "
        "[parameters: ('Jane Doe', '12 Main St')]"
    )

    assert "insert failed" in payload
    assert "INSERT INTO" not in payload
    assert "Jane Doe" not in payload
    assert "12 Main St" not in payload


def test_a_database_detail_line_never_reaches_the_payload() -> None:
    payload = _captured_payload(
        'duplicate key value violates unique constraint "uq_users_email"\n'
        "DETAIL:  Key (email)=(jane.doe) already exists."
    )

    assert "uq_users_email" in payload
    assert "DETAIL" not in payload
    assert "jane.doe" not in payload
