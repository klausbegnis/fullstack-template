from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Standard response envelope for successful requests."""

    success: bool = True
    message: str = "Success"
    data: T | None = None


class ErrorDetail(BaseModel):
    """Details for a failed API request."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard response envelope for failed requests."""

    error: ErrorDetail
    request_id: str | None = Field(
        default=None,
        description="Correlation ID of the request that produced this error",
    )


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Standard response envelope for paginated collections."""

    success: bool = True
    data: list[T]
    total: int = Field(description="Total number of items")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
