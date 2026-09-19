from typing import Any

from fastapi import APIRouter
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import BaseModel, Field
import pytest

from app.core import (
    REQUEST_ID_HEADER,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.main import app


class ErrorContractPayload(BaseModel):
    name: str = Field(min_length=3)


error_router = APIRouter(prefix="/__test/error-contract")


@error_router.post("/validation")
def validation_endpoint(payload: ErrorContractPayload) -> dict[str, str]:
    return {"name": payload.name}


@error_router.get("/conflict")
def conflict_endpoint() -> None:
    raise ConflictException("This resource already exists")


@error_router.get("/not-found")
def not_found_endpoint() -> None:
    raise NotFoundException()


@error_router.get("/unauthorized")
def unauthorized_endpoint() -> None:
    raise UnauthorizedException()


@error_router.get("/forbidden")
def forbidden_endpoint() -> None:
    raise ForbiddenException()


@error_router.get("/unexpected")
def unexpected_endpoint() -> None:
    raise RuntimeError("database password leaked")


app.include_router(error_router)


def _pop_verified_request_id(response: Response, body: dict[str, Any]) -> str:
    """Assert `body`'s `request_id` matches the echoed header and return it."""
    request_id = body.pop("request_id")
    assert isinstance(request_id, str)
    assert request_id
    assert response.headers[REQUEST_ID_HEADER] == request_id
    return request_id


@pytest.mark.integration
def test_validation_error_contract(error_client: TestClient) -> None:
    response = error_client.post(
        "/__test/error-contract/validation", json={"name": "x"}
    )

    assert response.status_code == 422
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {
        "error": {
            "code": "validation_error",
            "message": "Invalid request data",
            "details": {
                "errors": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "name"],
                        "msg": "String should have at least 3 characters",
                    }
                ]
            },
        }
    }


@pytest.mark.integration
def test_not_found_error_contract(error_client: TestClient) -> None:
    response = error_client.get("/__test/error-contract/not-found")

    assert response.status_code == 404
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {"error": {"code": "not_found", "message": "Resource not found"}}


@pytest.mark.integration
def test_conflict_error_contract(error_client: TestClient) -> None:
    response = error_client.get("/__test/error-contract/conflict")

    assert response.status_code == 409
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {
        "error": {
            "code": "conflict",
            "message": "This resource already exists",
        }
    }


@pytest.mark.integration
def test_unauthorized_error_contract(error_client: TestClient) -> None:
    response = error_client.get("/__test/error-contract/unauthorized")

    assert response.status_code == 401
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {
        "error": {"code": "unauthorized", "message": "Authentication required"}
    }


@pytest.mark.integration
def test_forbidden_error_contract(error_client: TestClient) -> None:
    response = error_client.get("/__test/error-contract/forbidden")

    assert response.status_code == 403
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {"error": {"code": "forbidden", "message": "Access forbidden"}}


@pytest.mark.integration
def test_unexpected_error_contract_does_not_leak_exception(
    error_client: TestClient,
) -> None:
    response = error_client.get("/__test/error-contract/unexpected")

    assert response.status_code == 500
    body = response.json()
    _pop_verified_request_id(response, body)
    assert body == {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred",
        }
    }
    assert "database password leaked" not in response.text
    assert "traceback" not in response.text.lower()


@pytest.mark.integration
def test_error_contract_generates_request_id_when_not_supplied(
    error_client: TestClient,
) -> None:
    response = error_client.get("/__test/error-contract/not-found")

    request_id = _pop_verified_request_id(response, response.json())
    assert len(request_id) == 36


@pytest.mark.integration
def test_error_contract_echoes_inbound_request_id(error_client: TestClient) -> None:
    response = error_client.get(
        "/__test/error-contract/not-found",
        headers={REQUEST_ID_HEADER: "caller-supplied-id"},
    )

    assert response.headers[REQUEST_ID_HEADER] == "caller-supplied-id"
    assert response.json()["request_id"] == "caller-supplied-id"
