from __future__ import annotations

from math import ceil
from typing import Annotated
import uuid

from fastapi import APIRouter, Query, status

from app.dependencies import RequireAdmin, SelfOrAdmin, UserServiceDep
from app.schemas.api import PaginatedResponse, SuccessResponse
from app.schemas.api.users import UserCreate, UserListFilters, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(
    _actor: RequireAdmin,
    service: UserServiceDep,
    filters: Annotated[UserListFilters, Query()],
) -> PaginatedResponse[UserRead]:
    items, total = await service.list_users(filters)
    total_pages = ceil(total / filters.page_size) if total else 0
    return PaginatedResponse(
        data=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=SuccessResponse[UserRead])
async def get_user(
    user_id: uuid.UUID,
    _actor: SelfOrAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.get_user(user_id)
    return SuccessResponse(data=data)


@router.post(
    "", response_model=SuccessResponse[UserRead], status_code=status.HTTP_201_CREATED
)
async def create_user(
    payload: UserCreate,
    _actor: RequireAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.create_user(payload)
    return SuccessResponse(message="User created", data=data)


@router.patch("/{user_id}", response_model=SuccessResponse[UserRead])
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    actor: SelfOrAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.update_user(actor, user_id, payload)
    return SuccessResponse(message="User updated", data=data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: uuid.UUID,
    _actor: RequireAdmin,
    service: UserServiceDep,
) -> None:
    await service.disable_user(user_id)


__all__ = ["router"]
