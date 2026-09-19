from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class AuthUserRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
