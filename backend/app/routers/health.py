from fastapi import APIRouter

from app.schemas.api import HealthResponse, SuccessResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> SuccessResponse[HealthResponse]:
    """Return the service health status."""
    return SuccessResponse(
        message="Service is healthy", data=HealthResponse(status="ok")
    )
