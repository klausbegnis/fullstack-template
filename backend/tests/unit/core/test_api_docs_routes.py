"""Verify the interactive docs and the schema are served only in development."""

from typing import Literal

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import api_docs_routes

DOC_PATHS = ("/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json")


def _client(environment: Literal["development", "production"]) -> TestClient:
    config = Settings(TESTING=True, ENVIRONMENT=environment, _env_file=None)
    return TestClient(FastAPI(**api_docs_routes(config)))


@pytest.mark.parametrize("path", DOC_PATHS)
def test_production_serves_no_docs_or_schema(path: str) -> None:
    assert _client("production").get(path).status_code == 404


@pytest.mark.parametrize("path", DOC_PATHS)
def test_development_serves_docs_and_schema(path: str) -> None:
    assert _client("development").get(path).status_code == 200


def test_production_is_the_default() -> None:
    config = Settings(TESTING=True, _env_file=None)

    assert set(api_docs_routes(config).values()) == {None}
