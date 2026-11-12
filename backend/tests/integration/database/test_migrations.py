import asyncio
from collections.abc import Iterator
import os

import pytest
from sqlalchemy import text

from app.config import Settings
from app.core.database import create_engine
from app.models.db_schemas import DOMAIN_SCHEMAS, INFRA_SCHEMA
from tests.support.scratch_database import ScratchDatabases, downgrade


@pytest.fixture(scope="module")
def scratch_databases() -> Iterator[ScratchDatabases]:
    databases = ScratchDatabases()
    yield databases
    databases.drop_templates()


def test_persistence_namespaces_and_version_table_exist() -> None:
    asyncio.run(_inspect_namespaces(os.environ["DATABASE_URL"]))


def test_downgrade_preserves_alembic_infrastructure(
    scratch_databases: ScratchDatabases,
) -> None:
    with scratch_databases.at("head") as url:
        downgrade(url, "base")
        asyncio.run(_assert_only_infra_remains(url))


async def _inspect_namespaces(database_url: str) -> None:
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


async def _assert_only_infra_remains(database_url: str) -> None:
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
