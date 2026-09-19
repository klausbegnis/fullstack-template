import asyncio
import os
import shutil
import subprocess

import pytest
from sqlalchemy import text

from app.config import Settings
from app.core.database import create_engine
from app.models.db_schemas import DOMAIN_SCHEMAS, INFRA_SCHEMA

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="PostgreSQL DATABASE_URL is not configured",
    ),
]


def test_persistence_namespaces_and_version_table_exist() -> None:
    asyncio.run(_inspect_namespaces())


def test_downgrade_preserves_alembic_infrastructure() -> None:
    alembic = shutil.which("alembic")
    if alembic is None:
        pytest.skip("Alembic executable is not available")
    environment = os.environ.copy()
    subprocess.run([alembic, "downgrade", "base"], check=True, env=environment)
    try:
        asyncio.run(_assert_only_infra_remains())
    finally:
        subprocess.run([alembic, "upgrade", "head"], check=True, env=environment)


async def _inspect_namespaces() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Settings(DATABASE_URL=database_url, TESTING=True)
    engine = create_engine(db_settings=config)
    try:
        async with engine.connect() as connection:
            namespaces = set(
                (
                    await connection.execute(
                        text(
                            "SELECT nspname FROM pg_namespace "
                            "WHERE nspname = ANY(:namespaces)"
                        ),
                        {"namespaces": [INFRA_SCHEMA, *DOMAIN_SCHEMAS]},
                    )
                ).scalars()
            )
            assert namespaces == {INFRA_SCHEMA, *DOMAIN_SCHEMAS}
            assert (
                await connection.scalar(
                    text("SELECT to_regclass('infra.alembic_version') IS NOT NULL")
                )
            ) is True
    finally:
        await engine.dispose()


async def _assert_only_infra_remains() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Settings(DATABASE_URL=database_url, TESTING=True)
    engine = create_engine(db_settings=config)
    try:
        async with engine.connect() as connection:
            namespaces = set(
                (
                    await connection.execute(
                        text(
                            "SELECT nspname FROM pg_namespace "
                            "WHERE nspname = ANY(:namespaces)"
                        ),
                        {"namespaces": [INFRA_SCHEMA, *DOMAIN_SCHEMAS]},
                    )
                ).scalars()
            )
            assert namespaces == {INFRA_SCHEMA}
            assert (
                await connection.scalar(
                    text("SELECT to_regclass('infra.alembic_version') IS NOT NULL")
                )
            ) is True
    finally:
        await engine.dispose()
