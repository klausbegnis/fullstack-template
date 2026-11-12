"""Explicit retention cleanup for rate-limit windows whose reset time has passed."""

import argparse
import asyncio

from app.config import settings
from app.core.clock import utc_now
from app.core.database import create_engine, create_session_factory
from app.repositories.rate_limit_windows import RateLimitWindowRepository
from app.services.rate_limits import RateLimitService, digest_key


async def run(*, limit: int = 500, dry_run: bool = False) -> int:
    """Delete up to `limit` ended windows, or only count them on a dry run."""
    if limit < 1:
        raise ValueError("limit must be positive")
    engine = create_engine(db_settings=settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            service = RateLimitService(
                session=session,
                windows=RateLimitWindowRepository(session),
                clock=utc_now,
                key=digest_key(settings.AUTH_JWT_SECRET.get_secret_value()),
            )
            return await service.purge_expired(limit=limit, dry_run=dry_run)
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
