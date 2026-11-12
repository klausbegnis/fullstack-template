from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

from app.core.error_alerts import ErrorAlertReporting, capture_error_alert
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
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code.lower()
        self.message = message
        self.details = details
        self.headers = headers
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


class TooManyRequestsException(APIException):
    """Exception for throttled requests (429) carrying a `Retry-After` header."""

    def __init__(
        self,
        retry_after_seconds: int,
        message: str = "Too many attempts. Try again later.",
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message=message,
            details={"retry_after_seconds": retry_after_seconds},
            headers={"Retry-After": str(retry_after_seconds)},
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
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard error envelope response, echoing the request ID."""
    content = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id,
    ).model_dump(exclude_none=True)
    response = JSONResponse(status_code=status_code, content=content, headers=headers)
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
        exc.status_code,
        exc.code,
        exc.message,
        exc.details,
        request_id=request_id,
        headers=exc.headers,
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
    """Convert an unhandled exception into a safe internal-error response.

    When the process reports alerts, the alert is captured here and delivered
    as the response's background task, after the unchanged 500 body is sent.
    """
    request_id = _request_id_of(request)
    logger.error(
        "Unhandled exception: %s",
        exc,
        exc_info=exc,
        extra={"request_id": request_id},
    )

    response = _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "An internal error occurred",
        request_id=request_id,
    )
    response.background = _error_alert_task(request, exc)
    return response


def _error_alert_task(request: Request, exc: Exception) -> BackgroundTask | None:
    """Capture the alert for `exc` as a task, or `None` when reporting is off."""
    reporter: ErrorAlertReporting | None = getattr(
        request.app.state, "error_alerts", None
    )
    if reporter is None or not reporter.enabled:
        return None
    try:
        alert = capture_error_alert(request, exc, reporter.now())
    except Exception as capture_error:
        logger.warning(
            "error alert not captured",
            extra={
                "request_id": _request_id_of(request),
                "error_type": type(capture_error).__name__,
            },
        )
        return None
    return BackgroundTask(reporter.report, alert)
