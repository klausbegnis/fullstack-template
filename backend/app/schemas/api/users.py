from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from app.models.user import UserRole
from app.schemas.api.names import DisplayName
from app.schemas.api.passwords import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


class UserCreate(BaseModel):
    name: DisplayName = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )
    role: UserRole = UserRole.MEMBER


class UserUpdate(BaseModel):
    name: DisplayName | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    role: UserRole | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListFilters(BaseModel):
    """Page-based pagination parameters for the users listing endpoint."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


__all__ = ["UserCreate", "UserListFilters", "UserRead", "UserUpdate"]
