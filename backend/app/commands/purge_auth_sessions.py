"""Explicit retention cleanup for expired/revoked authentication sessions."""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.config import settings
from app.core.database import create_engine, create_session_factory
from app.models.auth_session import AuthSession


async def run(*, limit: int = 500, dry_run: bool = False) -> int:
    if limit < 1:
        raise ValueError("limit must be positive")
    engine = create_engine(db_settings=settings)
    factory = create_session_factory(engine)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    try:
        async with factory() as session:
            query = (
                select(AuthSession.id)
                .where(
                    AuthSession.expires_at < cutoff,
                    (AuthSession.revoked_at < cutoff)
                    | AuthSession.revoked_at.is_(None),
                )
                .limit(limit)
            )
            ids = list((await session.scalars(query)).all())
            if not dry_run and ids:
                await session.execute(
                    delete(AuthSession).where(AuthSession.id.in_(ids))
                )
                await session.commit()
            return len(ids)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(asyncio.run(run(limit=args.limit, dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
