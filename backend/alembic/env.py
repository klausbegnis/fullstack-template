from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.models import Base
from app.models.db_schemas import DOMAIN_SCHEMAS, INFRA_SCHEMA

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ANN001
    """Limit autogenerate to the namespaces owned by this application."""
    if type_ == "schema":
        return name in (*DOMAIN_SCHEMAS, INFRA_SCHEMA)
    if type_ == "table":
        schema = getattr(object_, "schema", None) or "public"
        if schema not in (*DOMAIN_SCHEMAS, INFRA_SCHEMA):
            return False
        return not (schema == INFRA_SCHEMA and name == "alembic_version")
    return True


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        version_table="alembic_version",
        version_table_schema=INFRA_SCHEMA,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{INFRA_SCHEMA}"')
            )
            await connection.commit()
            await connection.run_sync(_configure)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    raise RuntimeError("Offline migrations are not supported; use a PostgreSQL URL.")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
