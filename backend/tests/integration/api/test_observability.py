import json
import logging

from fastapi.testclient import TestClient
import pytest

from app.core import REQUEST_ID_HEADER
from app.core.logger import JSONFormatter


@pytest.mark.integration
def test_request_id_is_generated_when_absent(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert len(request_id) == 36


@pytest.mark.integration
def test_request_id_is_echoed_when_supplied(client: TestClient) -> None:
    response = client.get("/health", headers={REQUEST_ID_HEADER: "my-correlation-id"})

    assert response.headers[REQUEST_ID_HEADER] == "my-correlation-id"


@pytest.mark.integration
def test_each_request_gets_its_own_request_id(client: TestClient) -> None:
    first = client.get("/health")
    second = client.get("/health")

    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


@pytest.mark.integration
def test_access_log_line_is_structured_json(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get(
            "/health", headers={REQUEST_ID_HEADER: "access-log-request-id"}
        )

    access_records = [
        record for record in caplog.records if record.name == "app.access"
    ]
    assert len(access_records) == 1

    record = access_records[0]
    assert record.http_method == "GET"  # type: ignore[attr-defined]
    assert record.http_path == "/health"  # type: ignore[attr-defined]
    assert record.http_status_code == response.status_code  # type: ignore[attr-defined]
    assert isinstance(record.duration_ms, float)  # type: ignore[attr-defined]

    payload = json.loads(JSONFormatter().format(record))
    assert payload["message"] == "request completed"
    assert payload["http_method"] == "GET"
    assert payload["http_path"] == "/health"
    assert payload["http_status_code"] == response.status_code
    assert payload["request_id"] == "access-log-request-id"
