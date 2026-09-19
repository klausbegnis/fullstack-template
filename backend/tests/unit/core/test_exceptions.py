import pytest

from app.core import (
    APIException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)


@pytest.mark.unit
def test_api_exception_stores_contract_fields() -> None:
    exc = APIException(418, "TEAPOT", "A test error", {"reason": "testing"})

    assert exc.status_code == 418
    assert exc.code == "teapot"
    assert exc.message == "A test error"
    assert exc.details == {"reason": "testing"}
    assert str(exc) == "A test error"


@pytest.mark.unit
def test_not_found_exception() -> None:
    exc = NotFoundException("Test resource not found")

    assert exc.status_code == 404
    assert exc.code == "not_found"
    assert exc.message == "Test resource not found"
    assert exc.details is None


@pytest.mark.unit
def test_not_found_exception_default_message() -> None:
    exc = NotFoundException()

    assert exc.status_code == 404
    assert exc.code == "not_found"
    assert exc.message == "Resource not found"


@pytest.mark.unit
def test_validation_exception() -> None:
    exc = ValidationException("Test validation failed")

    assert exc.status_code == 422
    assert exc.code == "validation_error"
    assert exc.message == "Test validation failed"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exception_type", "status_code", "code"),
    [
        (UnauthorizedException, 401, "unauthorized"),
        (ForbiddenException, 403, "forbidden"),
        (ConflictException, 409, "conflict"),
    ],
)
def test_http_exception_defaults(
    exception_type: type[APIException], status_code: int, code: str
) -> None:
    exc = exception_type()

    assert exc.status_code == status_code
    assert exc.code == code
    assert exc.message
    assert exc.details is None
