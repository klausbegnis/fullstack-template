"""Enforce the persistence contract every mapped table must satisfy.

A table without an explicit schema lands in `public`, where `alembic check`
cannot see it and autogenerate silently skips it. A constraint that was named by
hand drifts from the convention in `models/base.py` and produces a migration that
cannot be reversed. Both are checked against the live metadata, so a new model is
covered by importing it in `app/models/__init__.py`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Table

import app.models
from app.models.base import NAMING_CONVENTION, Base
from app.models.db_schemas import DOMAIN_SCHEMAS

PRIMARY_KEY_CONVENTION = NAMING_CONVENTION["pk"]
TABLES = sorted(Base.metadata.tables.values(), key=lambda table: table.fullname)


def test_models_are_registered_by_import_side_effect() -> None:
    assert app.models.Base is Base
    assert TABLES, (
        "no tables in Base.metadata; a new model must be imported in "
        "app/models/__init__.py or alembic autogenerate will not see it"
    )


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.fullname)
def test_table_pins_a_domain_schema(table: Table) -> None:
    assert table.schema in DOMAIN_SCHEMAS, (
        f"{table.name} pins schema {table.schema!r}; every table belongs to a "
        f"bounded context declared in app/models/db_schemas.py {DOMAIN_SCHEMAS}"
    )


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.fullname)
def test_table_primary_key_follows_the_naming_convention(table: Table) -> None:
    expected = PRIMARY_KEY_CONVENTION % {"table_name": table.name}
    assert table.primary_key.name == expected, (
        f"{table.fullname} has primary key {table.primary_key.name!r}; the "
        f"convention in app/models/base.py produces {expected!r}, so this one was "
        f"named by hand"
    )
