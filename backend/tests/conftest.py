import os

from fastapi.testclient import TestClient
import pytest

from tests.support.worker_database import (
    drop_worker_database,
    worker_database_environment,
)

os.environ.setdefault("TESTING", "true")
os.environ.update(worker_database_environment())

from app.main import app


def pytest_unconfigure() -> None:
    """Drop this xdist worker's database once the worker has finished."""
    drop_worker_database()


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def error_client() -> TestClient:
    """Return a client that exposes the application's 500 response."""
    return TestClient(app, raise_server_exceptions=False)
