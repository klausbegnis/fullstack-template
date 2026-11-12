"""Unit tests for `RateLimitService`: digests, retry-after and purge, DB-free."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import hashlib

from app.services.rate_limits import RateLimitService, subject_digest
from tests.support.fakes import FakeSession
from tests.support.rate_limit_fakes import FakeRateLimitWindowStore, StoredWindow

START = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


class MovableClock:
    """A wall clock the test moves forward by hand."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


def _service(
    store: FakeRateLimitWindowStore, clock: MovableClock
) -> tuple[RateLimitService, FakeSession]:
    session = FakeSession()
    service = RateLimitService(
        session=session,  # type: ignore[arg-type]
        windows=store,
        clock=clock,
    )
    return service, session


def test_hits_up_to_the_limit_pass_and_the_next_reports_the_wait() -> None:
    store = FakeRateLimitWindowStore()
    clock = MovableClock()
    service, _ = _service(store, clock)

    async def scenario() -> list[int | None]:
        results = [
            await service.hit(
                "login:subject", "member@example.test", limit=2, window_seconds=900
            )
            for _ in range(2)
        ]
        clock.now = START + timedelta(seconds=100)
        results.append(
            await service.hit(
                "login:subject", "member@example.test", limit=2, window_seconds=900
            )
        )
        return results

    assert asyncio.run(scenario()) == [None, None, 800]


def test_a_blocked_hit_reports_at_least_one_second() -> None:
    store = FakeRateLimitWindowStore()
    clock = MovableClock()
    service, _ = _service(store, clock)

    async def scenario() -> int | None:
        await service.hit("login:ip", "203.0.113.7", limit=1, window_seconds=10)
        clock.now = START + timedelta(seconds=9, milliseconds=900)
        return await service.hit("login:ip", "203.0.113.7", limit=1, window_seconds=10)

    assert asyncio.run(scenario()) == 1


def test_each_hit_commits_its_own_transaction() -> None:
    store = FakeRateLimitWindowStore()
    service, session = _service(store, MovableClock())

    async def scenario() -> None:
        await service.hit("login:ip", "203.0.113.7", limit=5, window_seconds=60)
        await service.hit("login:ip", "203.0.113.7", limit=5, window_seconds=60)

    asyncio.run(scenario())

    assert (session.commits, session.rollbacks) == (2, 0)


def test_the_store_receives_the_sha256_digest_never_the_subject() -> None:
    store = FakeRateLimitWindowStore()
    service, _ = _service(store, MovableClock())

    asyncio.run(
        service.hit("login:subject", "member@example.test", limit=5, window_seconds=60)
    )

    expected = hashlib.sha256(b"member@example.test").digest()
    assert list(store.windows) == [("login:subject", expected)]
    assert len(subject_digest("member@example.test")) == 32


def test_purge_deletes_only_ended_windows_up_to_the_limit() -> None:
    store = FakeRateLimitWindowStore(
        windows={
            ("login:ip", b"a" * 32): StoredWindow(
                hits=1, resets_at=START - timedelta(hours=2)
            ),
            ("login:ip", b"b" * 32): StoredWindow(
                hits=1, resets_at=START - timedelta(hours=1)
            ),
            ("login:ip", b"c" * 32): StoredWindow(
                hits=1, resets_at=START + timedelta(hours=1)
            ),
        }
    )
    service, session = _service(store, MovableClock())

    deleted = asyncio.run(service.purge_expired(limit=1, dry_run=False))

    assert deleted == 1
    assert sorted(key[1] for key in store.windows) == [b"b" * 32, b"c" * 32]
    assert session.commits == 1


def test_a_dry_run_purge_counts_without_deleting() -> None:
    store = FakeRateLimitWindowStore(
        windows={
            ("login:ip", b"a" * 32): StoredWindow(
                hits=1, resets_at=START - timedelta(hours=1)
            ),
            ("login:ip", b"c" * 32): StoredWindow(
                hits=1, resets_at=START + timedelta(hours=1)
            ),
        }
    )
    service, _ = _service(store, MovableClock())

    counted = asyncio.run(service.purge_expired(limit=500, dry_run=True))

    assert counted == 1
    assert len(store.windows) == 2
