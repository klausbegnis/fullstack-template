"""Block until the configured PostgreSQL database accepts connections."""

import argparse
import asyncio
import sys
import time

from app.config import settings
from app.core.database import create_engine, verify_connection


async def wait_for_database(*, timeout_seconds: float, interval_seconds: float) -> None:
    """Poll the database until reachable, raising once `timeout_seconds` elapse."""
    deadline = time.monotonic() + timeout_seconds
    engine = create_engine(db_settings=settings)
    try:
        while True:
            try:
                await verify_connection(engine)
                return
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(interval_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    """Run the database wait loop from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    args = parser.parse_args()
    try:
        asyncio.run(
            wait_for_database(
                timeout_seconds=args.timeout_seconds,
                interval_seconds=args.interval_seconds,
            )
        )
    except Exception as exc:
        print(f"Database did not become ready: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
