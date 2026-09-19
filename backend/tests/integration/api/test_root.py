from fastapi.testclient import TestClient
import pytest


@pytest.mark.integration
def test_read_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "app": "Backend API",
        "version": "0.1.0",
        "message": "Hello, World!",
    }


@pytest.mark.integration
def test_api_returns_json(client: TestClient) -> None:
    response = client.get("/")

    assert response.headers["content-type"] == "application/json"
