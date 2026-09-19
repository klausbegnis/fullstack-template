import os

from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("TESTING", "true")

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def error_client() -> TestClient:
    """Return a client that exposes the application's 500 response."""
    return TestClient(app, raise_server_exceptions=False)
