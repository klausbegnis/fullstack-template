from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_event import SecurityEvent


class SecurityEventRepository:
    """Append security events through one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        action: str,
        user_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        payload: dict[str, object],
    ) -> SecurityEvent:
        """Store one event and flush so it is part of the caller's transaction."""
        event = SecurityEvent(
            action=action,
            user_id=user_id,
            actor_user_id=actor_user_id,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event
