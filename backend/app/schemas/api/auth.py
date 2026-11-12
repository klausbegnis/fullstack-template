from __future__ import annotations

from datetime import datetime
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


class AuthSessionExpiry(BaseModel):
    """When the issued access token and the whole session stop being valid."""

    access_expires_at: datetime
    session_expires_at: datetime


class AuthLoginRead(AuthUserRead):
    """The signed-in identity plus the expiry of the session just opened."""

    access_expires_at: datetime
    session_expires_at: datetime
