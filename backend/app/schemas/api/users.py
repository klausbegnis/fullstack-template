from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    role: UserRole = UserRole.MEMBER


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
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
