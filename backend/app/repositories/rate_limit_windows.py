"""Persistence of the fixed rate-limit windows every worker shares."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit_window import RateLimitWindow


@dataclass(frozen=True, slots=True)
class WindowCount:
    """The hits of one window after a hit, and when that window resets."""

    hits: int
    resets_at: datetime


class RateLimitWindowRepository:
    """Count hits per `(scope, subject_digest)` and delete windows that ended."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def hit(
        self,
        scope: str,
        subject_digest: bytes,
        *,
        now: datetime,
        window: timedelta,
    ) -> WindowCount:
        """Count one hit in one atomic upsert; an ended window restarts at 1."""
        resets_at = now + window
        statement = insert(RateLimitWindow).values(
            id=uuid.uuid4(),
            scope=scope,
            subject_digest=subject_digest,
            resets_at=resets_at,
            hits=1,
        )
        ended = RateLimitWindow.resets_at <= now
        upsert = statement.on_conflict_do_update(
            index_elements=[RateLimitWindow.scope, RateLimitWindow.subject_digest],
            set_={
                "hits": case((ended, 1), else_=RateLimitWindow.hits + 1),
                "resets_at": case((ended, resets_at), else_=RateLimitWindow.resets_at),
            },
        ).returning(RateLimitWindow.hits, RateLimitWindow.resets_at)
        row = (await self._session.execute(upsert)).one()
        await self._session.flush()
        return WindowCount(hits=row.hits, resets_at=row.resets_at)

    async def count_expired(self, *, before: datetime, limit: int) -> int:
        """Count up to `limit` windows that reset at or before `before`."""
        expired = (
            select(RateLimitWindow.id)
            .where(RateLimitWindow.resets_at <= before)
            .limit(limit)
            .subquery()
        )
        return (
            await self._session.scalar(select(func.count()).select_from(expired))
        ) or 0

    async def delete_expired(self, *, before: datetime, limit: int) -> int:
        """Delete up to `limit` windows that reset at or before `before`."""
        ids = list(
            (
                await self._session.scalars(
                    select(RateLimitWindow.id)
                    .where(RateLimitWindow.resets_at <= before)
                    .order_by(RateLimitWindow.resets_at)
                    .limit(limit)
                )
            ).all()
        )
        if ids:
            await self._session.execute(
                delete(RateLimitWindow).where(RateLimitWindow.id.in_(ids))
            )
            await self._session.flush()
        return len(ids)
