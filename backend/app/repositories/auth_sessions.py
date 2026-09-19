from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_session import AuthRefreshToken, AuthSession
from app.models.user import User


class AuthSessionRepository:
    """Persist authentication sessions through one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, user: User, csrf_hash: bytes, expires_at: datetime
    ) -> AuthSession:
        value = AuthSession(
            user_id=user.id, csrf_token_hash=csrf_hash, expires_at=expires_at
        )
        self._session.add(value)
        await self._session.flush()
        return value

    async def add_refresh(
        self,
        *,
        auth_session: AuthSession,
        secret_hash: bytes,
        expires_at: datetime,
    ) -> AuthRefreshToken:
        token = AuthRefreshToken(
            session_id=auth_session.id,
            secret_hash=secret_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_active(
        self, session_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthSession | None:
        query = (
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.id == session_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
                User.disabled_at.is_(None),
            )
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.execute(query)
        pair: Row[tuple[AuthSession, User]] | None = row.first()
        if not pair:
            return None
        auth_session: AuthSession = pair[0]
        user: User = pair[1]
        auth_session.user = user
        return auth_session

    async def get_by_id(
        self, session_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthSession | None:
        query = select(AuthSession).where(AuthSession.id == session_id)
        if for_update:
            query = query.with_for_update()
        result: AuthSession | None = await self._session.scalar(query)
        return result

    async def get_token(
        self, token_id: uuid.UUID, *, for_update: bool = False
    ) -> AuthRefreshToken | None:
        query = select(AuthRefreshToken).where(AuthRefreshToken.id == token_id)
        if for_update:
            query = query.with_for_update()
        result: AuthRefreshToken | None = await self._session.scalar(query)
        return result

    async def revoke(self, auth_session: AuthSession, reason: str) -> None:
        auth_session.revoked_at = datetime.now(UTC)
        auth_session.revocation_reason = reason[:80]
        await self._session.execute(
            update(AuthRefreshToken)
            .where(AuthRefreshToken.session_id == auth_session.id)
            .values(revoked_at=datetime.now(UTC))
        )
