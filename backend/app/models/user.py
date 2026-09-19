from __future__ import annotations

from datetime import datetime
import enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from .base import Base

if TYPE_CHECKING:
    from .auth_session import AuthSession


class UserRole(enum.StrEnum):
    """Roles recognized by the platform's role-based access control."""

    ADMIN = "admin"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email_normalized = lower(btrim(email))",
            name="email_normalized_matches_email",
        ),
        CheckConstraint(
            "password_hash LIKE '$argon2id$%'", name="password_hash_argon2id"
        ),
        UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        Index("ix_users_email_normalized", "email_normalized"),
        {"schema": "iam"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            schema="iam",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.MEMBER,
        server_default=UserRole.MEMBER.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
