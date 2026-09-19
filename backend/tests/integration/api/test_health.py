from fastapi.testclient import TestClient
import pytest


@pytest.mark.integration
def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Service is healthy",
        "data": {"status": "ok"},
    }


@pytest.mark.integration
def test_health_returns_json(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["content-type"] == "application/json"
