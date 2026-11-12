"""Disposable PostgreSQL databases for the migration tests.

A migration test that runs `alembic downgrade`, or upgrades through an old
revision, never touches the shared `DATABASE_URL` database: other tests leave
rows there, and a parallel worker would see its schema mid-downgrade. It works
on a scratch database created on the same server instead.

Bringing a fresh database from base to a revision costs a subprocess and every
step in between, so `ScratchDatabases` migrates one template database per start
revision once per session and clones each scratch database from it with
`CREATE DATABASE ... TEMPLATE`, which copies the files without replaying the
migrations. Template and scratch names carry the pytest-xdist worker id and a
per-session token, so neither parallel workers nor two concurrent runs against
the same server ever share or drop each other's databases.

Alembic runs as a subprocess because `app.config.settings` binds `DATABASE_URL`
when it is first imported; the subprocess reads the scratch URL from its own
environment instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "base"

Params = Mapping[str, object]
Statement = tuple[str, Params]


def worker_id() -> str:
    """Return the pytest-xdist worker id, or `main` for a serial run."""
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def database_url(name: str, *, server_url: str | None = None) -> str:
    """Return the URL of database `name` on the server of `server_url`."""
    return (
        make_url(server_url or os.environ["DATABASE_URL"])
        .set(database=name)
        .render_as_string(hide_password=False)
    )


async def _administer(statements: Sequence[str], server_url: str | None) -> None:
    engine = create_async_engine(
        server_url or os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def administer(statements: Sequence[str], *, server_url: str | None = None) -> None:
    """Run server-level `statements` (roles, databases) outside a transaction."""
    asyncio.run(_administer(statements, server_url))


def create_database(
    name: str, *, template: str | None = None, server_url: str | None = None
) -> None:
    """Drop any leftover database called `name` and create it, optionally cloned."""
    clone = f' TEMPLATE "{template}"' if template else ""
    asyncio.run(
        _administer(
            (
                f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',
                f'CREATE DATABASE "{name}"{clone}',
            ),
            server_url,
        )
    )


def drop_database(name: str, *, server_url: str | None = None) -> None:
    """Drop database `name`, closing any connection a test left open."""
    asyncio.run(
        _administer((f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',), server_url)
    )


def alembic(url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run an Alembic command against `url` and return the finished process."""
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": url,
            "TESTING": "true",
        },
        capture_output=True,
        text=True,
        check=False,
    )


def run_alembic(url: str, *arguments: str) -> str:
    """Run an Alembic command that must succeed and return its combined output."""
    result = alembic(url, *arguments)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    return output


def upgrade(url: str, revision: str) -> None:
    """Upgrade `url` to `revision`, failing the test with Alembic's output."""
    run_alembic(url, "upgrade", revision)


def downgrade(url: str, revision: str) -> None:
    """Downgrade `url` to `revision`, failing the test with Alembic's output."""
    run_alembic(url, "downgrade", revision)


async def fetch(
    url: str, statement: str, params: Params | None = None
) -> list[tuple[object, ...]]:
    """Return every row of `statement` as plain tuples."""
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text(statement), dict(params or {}))
            return [tuple(row) for row in rows]
    finally:
        await engine.dispose()


async def execute(url: str, statements: Sequence[str | Statement]) -> None:
    """Run `statements` in one transaction; each is SQL or `(SQL, params)`."""
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            for statement in statements:
                sql, params = (
                    (statement, {}) if isinstance(statement, str) else statement
                )
                await connection.execute(text(sql), dict(params))
    finally:
        await engine.dispose()


class ScratchDatabases:
    """Clone disposable databases from per-revision templates migrated once."""

    def __init__(self) -> None:
        self._prefix = f"scratch_{worker_id()}_{uuid.uuid4().hex[:8]}"
        self._templates: dict[str, str] = {}

    def _template(self, revision: str) -> str:
        if revision not in self._templates:
            slug = re.sub(r"[^a-z0-9]", "_", revision.lower())
            name = f"{self._prefix}_tpl_{slug}"
            create_database(name)
            try:
                upgrade(database_url(name), revision)
            except BaseException:
                drop_database(name)
                raise
            self._templates[revision] = name
        return self._templates[revision]

    @contextmanager
    def at(self, revision: str) -> Iterator[str]:
        """Yield the URL of a fresh database at `revision`, dropped afterwards."""
        template = None if revision == BASE_REVISION else self._template(revision)
        name = f"{self._prefix}_{uuid.uuid4().hex[:12]}"
        create_database(name, template=template)
        try:
            yield database_url(name)
        finally:
            drop_database(name)

    def drop_templates(self) -> None:
        """Drop every template this session migrated."""
        for name in self._templates.values():
            drop_database(name)
        self._templates.clear()
