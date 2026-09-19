import json
import logging
import sys

import pytest

from app.core.logger import JSONFormatter, RequestIdFilter
from app.core.request_context import bind_request_id, reset_request_id


def _make_record(
    message: str = "hello", *, extra: dict[str, object] | None = None
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


@pytest.mark.unit
def test_json_formatter_emits_required_fields() -> None:
    record = _make_record("hello world")

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.tests"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
    assert "request_id" not in payload


@pytest.mark.unit
def test_json_formatter_includes_request_id_when_present() -> None:
    record = _make_record("with id", extra={"request_id": "abc-123"})

    payload = json.loads(JSONFormatter().format(record))

    assert payload["request_id"] == "abc-123"


@pytest.mark.unit
def test_json_formatter_includes_arbitrary_extra_fields() -> None:
    record = _make_record("access", extra={"http_method": "GET", "duration_ms": 12.5})

    payload = json.loads(JSONFormatter().format(record))

    assert payload["http_method"] == "GET"
    assert payload["duration_ms"] == 12.5


@pytest.mark.unit
def test_json_formatter_serializes_exception_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.tests",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JSONFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


@pytest.mark.unit
def test_request_id_filter_populates_from_context() -> None:
    token = bind_request_id("context-request-id")
    try:
        record = _make_record("from context")
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "context-request-id"  # type: ignore[attr-defined]
    finally:
        reset_request_id(token)


@pytest.mark.unit
def test_request_id_filter_does_not_override_explicit_value() -> None:
    record = _make_record("explicit", extra={"request_id": "explicit-id"})

    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "explicit-id"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_request_id_filter_defaults_to_none_outside_request_context() -> None:
    record = _make_record("no context")

    assert RequestIdFilter().filter(record) is True
    assert record.request_id is None  # type: ignore[attr-defined]
