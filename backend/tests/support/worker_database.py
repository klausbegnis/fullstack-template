"""Point each pytest-xdist worker at its own migrated PostgreSQL database.

Integration tests share whatever database `DATABASE_URL` names and leave rows
in it, and `app.config.settings` binds that URL the first time the app is
imported. Under `pytest -n <N>` each worker therefore rewrites `DATABASE_URL`
before `tests/conftest.py` imports the app: it derives
`<database>_<worker>_<run>` on the same server (`<run>` is a prefix of xdist's
test-run id, so two concurrent runs never collide), creates it, runs
`alembic upgrade head` on it and exports the new URL, so no worker ever sees
another worker's rows. `drop_worker_database` removes it when the worker ends.

A serial run (no `PYTEST_XDIST_WORKER`) and a run without `DATABASE_URL` are
left untouched.
"""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url

from tests.support.scratch_database import (
    create_database,
    database_url,
    drop_database,
    upgrade,
)

SERVER_URL_VARIABLE = "TEST_SERVER_DATABASE_URL"


def worker_database_name(server_url: str, worker: str, run: str) -> str:
    """Return the database name worker `worker` of run `run` uses."""
    return f"{make_url(server_url).database}_{worker}_{run[:8]}"


def worker_database_environment() -> dict[str, str]:
    """Create and migrate this xdist worker's database; return its environment.

    The result points `DATABASE_URL` at the worker database and remembers the
    original URL for `drop_worker_database`; it is empty outside xdist or
    without a configured database, so the caller can always apply it.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    server_url = os.environ.get("DATABASE_URL")
    if not worker or not server_url or os.environ.get(SERVER_URL_VARIABLE):
        return {}
    run = os.environ.get("PYTEST_XDIST_TESTRUNUID", "run")
    name = worker_database_name(server_url, worker, run)
    url = database_url(name, server_url=server_url)
    create_database(name, server_url=server_url)
    upgrade(url, "head")
    return {"DATABASE_URL": url, SERVER_URL_VARIABLE: server_url}


def drop_worker_database() -> None:
    """Drop the database `worker_database_environment` created, if any."""
    server_url = os.environ.get(SERVER_URL_VARIABLE)
    if not server_url:
        return
    name = make_url(os.environ["DATABASE_URL"]).database
    if name:
        drop_database(name, server_url=server_url)
