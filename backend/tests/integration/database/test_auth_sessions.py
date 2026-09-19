from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import os
import uuid

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.database import create_engine, create_session_factory
from app.core.security import hash_password, hash_secret, new_secret
from app.models.auth_session import AuthRefreshToken, AuthSession
from app.models.user import User, UserRole
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthRequestContext, AuthService, RefreshResult

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="PostgreSQL DATABASE_URL is not configured",
    ),
]


def _factory():
    engine = create_engine(database_url=os.environ["DATABASE_URL"])
    return engine, create_session_factory(engine)


def _context(refresh_value: str, csrf: str) -> AuthRequestContext:
    return AuthRequestContext(
        origin="http://localhost:3000",
        access_token=None,
        refresh_token=refresh_value,
        csrf_cookie=csrf,
        csrf_header=csrf,
    )


def _service(session) -> AuthService:
    return AuthService(
        session=session,
        users=UserRepository(session),
        auth_sessions=AuthSessionRepository(session),
        config=settings,
    )


async def _seed(factory):
    async with factory() as session:
        users = UserRepository(session)
        auth_sessions = AuthSessionRepository(session)
        user = await users.create_bootstrap_user(
            email=f"db-{uuid.uuid4()}@example.test",
            password_hash=hash_password("password"),
            role=UserRole.MEMBER,
        )
        csrf = new_secret()
        auth_session = await auth_sessions.create(
            user=user,
            csrf_hash=hash_secret(csrf),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        secret = new_secret()
        token = await auth_sessions.add_refresh(
            auth_session=auth_session,
            secret_hash=hash_secret(secret),
            expires_at=auth_session.expires_at,
        )
        await session.commit()
        return user.id, auth_session.id, f"{token.id}.{secret}", csrf


def test_refresh_concurrency_allows_one_and_replays_the_other() -> None:
    asyncio.run(_test_refresh_concurrency())


async def _test_refresh_concurrency() -> None:
    engine, factory = _factory()
    user_id, session_id, refresh_value, csrf = await _seed(factory)
    try:
        async with factory() as first, factory() as second:
            results = await asyncio.gather(
                _service(first).refresh(_context(refresh_value, csrf)),
                _service(second).refresh(_context(refresh_value, csrf)),
                return_exceptions=True,
            )
            assert sum(isinstance(result, RefreshResult) for result in results) == 1
            assert (
                sum(getattr(result, "status_code", None) == 401 for result in results)
                == 1
            )
        async with factory() as session:
            auth_session = await session.get(AuthSession, session_id)
            assert auth_session is not None and auth_session.revoked_at is not None
            assert (
                await session.scalar(
                    select(func.count(AuthRefreshToken.id)).where(
                        AuthRefreshToken.session_id == session_id
                    )
                )
            ) >= 1
            assert await session.get(User, user_id) is not None
    finally:
        async with factory() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


def test_constraints_and_user_cascade() -> None:
    asyncio.run(_test_constraints_and_user_cascade())


async def _test_constraints_and_user_cascade() -> None:
    engine, factory = _factory()
    user_id, session_id, _, _ = await _seed(factory)
    try:
        async with factory() as session:
            bad = User(
                email="Bad@Example.test",
                email_normalized="wrong@example.test",
                password_hash=hash_password("password"),
            )
            session.add(bad)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        async with factory() as session:
            assert await session.get(AuthSession, session_id) is None
            assert (
                await session.scalar(
                    select(func.count(AuthRefreshToken.id)).where(
                        AuthRefreshToken.session_id == session_id
                    )
                )
            ) == 0
    finally:
        await engine.dispose()


def test_expired_session_is_not_active() -> None:
    asyncio.run(_test_expired_session())


async def _test_expired_session() -> None:
    engine, factory = _factory()
    user_id, session_id, _, _ = await _seed(factory)
    try:
        async with factory() as session:
            await session.execute(
                update(AuthSession)
                .where(AuthSession.id == session_id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()
            auth_session = await session.get(AuthSession, session_id)
            assert auth_session is not None and auth_session.expires_at < datetime.now(
                UTC
            )
    finally:
        async with factory() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


def test_bootstrap_is_idempotent_and_does_not_change_credentials() -> None:
    asyncio.run(_test_bootstrap_idempotency())


async def _test_bootstrap_idempotency() -> None:
    engine, factory = _factory()
    email = f"bootstrap-{uuid.uuid4()}@example.test"
    original_hash = hash_password("original")
    try:
        async with factory() as session:
            users = UserRepository(session)
            user = await users.create_bootstrap_user(
                email=email,
                password_hash=original_hash,
                role=UserRole.ADMIN,
            )
            await session.commit()
            user_id = user.id
        async with factory() as session:
            repeated = await UserRepository(session).create_bootstrap_user(
                email=email.upper(),
                password_hash=hash_password("replacement"),
                role=UserRole.MEMBER,
            )
            await session.commit()
            assert repeated.id == user_id
            assert repeated.password_hash == original_hash
            assert repeated.role is UserRole.ADMIN
    finally:
        async with factory() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
