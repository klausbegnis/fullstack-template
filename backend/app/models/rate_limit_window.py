from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from .base import Base


class RateLimitWindow(Base):
    """A fixed rate-limit window shared by every worker, keyed by scope and subject.

    Only the SHA-256 digest of the subject (an email or an IP) is stored, never
    the plain value.
    """

    __tablename__ = "rate_limit_windows"
    __table_args__ = (
        UniqueConstraint("scope", "subject_digest"),
        Index("ix_rate_limit_windows_resets_at", "resets_at"),
        {"schema": "iam"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    resets_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
