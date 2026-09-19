from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.core.middleware import REQUEST_ID_HEADER
from app.schemas.api import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


class APIException(Exception):  # noqa: N818
    """Base exception for API errors with an HTTP status and stable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code.lower()
        self.message = message
        self.details = details
        super().__init__(self.message)


class NotFoundException(APIException):
    """Exception for resource not found errors (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message=message,
            details=details,
        )


class ValidationException(APIException):
    """Exception for validation errors (422)."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message=message,
            details=details,
        )


class UnauthorizedException(APIException):
    """Exception for authentication errors (401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message=message,
            details=details,
        )


class ForbiddenException(APIException):
    """Exception for authorization errors (403)."""

    def __init__(
        self,
        message: str = "Access forbidden",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=message,
            details=details,
        )


class ConflictException(APIException):
    """Exception for resource conflict errors (409)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: dict[str, Any] | None = None,
        code: str = "conflict",
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message,
            details=details,
        )


def _request_id_of(request: Request) -> str | None:
    """Return the request ID bound by `RequestIDMiddleware`, if any."""
    return getattr(request.state, "request_id", None)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    request_id: str | None = None,
) -> JSONResponse:
    """Build the standard error envelope response, echoing the request ID."""
    content = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id,
    ).model_dump(exclude_none=True)
    response = JSONResponse(status_code=status_code, content=content)
    if request_id is not None:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Convert a domain API exception into the standard error envelope."""
    request_id = _request_id_of(request)
    logger.warning(
        "API exception: %s - %s - Path: %s",
        exc.code,
        exc.message,
        request.url.path,
        extra={"request_id": request_id},
    )

    return _error_response(
        exc.status_code, exc.code, exc.message, exc.details, request_id=request_id
    )


def _sanitize_validation_errors(
    errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only stable, JSON-safe fields from Pydantic validation errors."""
    sanitized = []
    for error in errors:
        location = error.get("loc", ())
        if not isinstance(location, (list, tuple)):
            location = (location,)
        sanitized.append(
            {
                "type": str(error.get("type", "")),
                "loc": list(location),
                "msg": str(error.get("msg", "")),
            }
        )
    return sanitized


def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert a FastAPI validation error into the standard error envelope."""
    request_id = _request_id_of(request)
    errors = _sanitize_validation_errors(exc.errors())
    logger.warning(
        "Validation error on %s: %s",
        request.url.path,
        errors,
        extra={"request_id": request_id},
    )

    return _error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Invalid request data",
        {"errors": errors},
        request_id=request_id,
    )


def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert an unhandled exception into a safe internal-error response."""
    request_id = _request_id_of(request)
    logger.error(
        "Unhandled exception: %s",
        exc,
        exc_info=exc,
        extra={"request_id": request_id},
    )

    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "An internal error occurred",
        request_id=request_id,
    )
