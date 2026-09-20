---
paths:
  - "backend/app/models/**"
  - "backend/app/repositories/**"
  - "backend/alembic/**"
---

Rules for the mapped tables, the repositories that read and write them, and the Alembic
revisions that keep the database in step with both. Layer import rules live in
`backend/layering.md`; the service-side transaction recipe lives in `backend/api-crud.md`.

### Pin every table to a schema in `DOMAIN_SCHEMAS`

This repo is schema-per-bounded-context. A table with no `schema` lands in `public`, where
Alembic's `include_schemas` filter cannot see it, so autogenerate silently emits nothing and
the migration looks clean. A new bounded context adds its schema to `app/models/db_schemas.py`
before the first model that uses it.

**Incorrect:**

```python
class User(Base):
    __tablename__ = "users"
    # DO NOT DO THIS
    __table_args__ = (UniqueConstraint("email_normalized", name="uq_users_email_normalized"),)
```

**Correct:**

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        Index("ix_users_email_normalized", "email_normalized"),
        {"schema": "iam"},
    )
```

Enforced by: backend/tests/unit/architecture/test_model_contracts.py, alembic check

### Let the naming convention name every constraint

`NAMING_CONVENTION` in `app/models/base.py` derives index, unique, check, foreign-key and
primary-key names from the table and column. A hand-picked name that does not match the
pattern makes autogenerate see a rename on the next run and emit a drop-and-create.

Enforced by: alembic check

### Give every entity a UUID key, tz-aware timestamps and a reversible disable

Entities carry a `uuid.UUID` primary key defaulted in Python, `created_at`/`updated_at` as
`DateTime(timezone=True)` with `server_default=func.now()`, and — when removal must be
reversible — `disabled_at` rather than a row delete. A naive timestamp column compares wrong
against the tz-aware values asyncpg returns.

Enforced by: scaffold: .agents/scaffold/backend_crud.py, review

### Create enum types explicitly in the migration

PostgreSQL enum types are created outside the table DDL. Autogenerate emits `sa.Enum(...)`
inside `create_table` without a matching `CREATE TYPE`, so the upgrade fails on a fresh
database and the downgrade leaves the type behind.

**Incorrect:**

```python
def upgrade() -> None:
    op.create_table(
        "users",
        # DO NOT DO THIS
        sa.Column("role", sa.Enum("admin", "member", name="user_role"), nullable=False),
        schema="iam",
    )
```

**Correct:**

```python
def upgrade() -> None:
    user_role = sa.Enum("admin", "member", name="user_role", schema="iam")
    user_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("role", sa.Enum(name="user_role", schema="iam", create_type=False), nullable=False),
        schema="iam",
    )
```

Enforced by: backend/tests/unit/architecture/test_migration_contracts.py

### Generate migrations with `create_migration` and never edit a merged revision

`uv run python -m app.commands.create_migration -m "<msg>"` autogenerates the revision, strips
the banner comments Alembic injects, and runs ruff over the result, so the file is compliant
with no manual cleanup. A revision that already exists on `origin/main` has run on someone's
database: change it and their history diverges silently. Fix it forward with a new revision,
and keep exactly one head.

Enforced by: hook: .agents/hooks/guard_paths.py, backend/tests/unit/architecture/test_migration_contracts.py, alembic check

### Write queries in SQLAlchemy 2.0 `select()` style

`Query`-era APIs are legacy and do not type-check under strict mypy against `AsyncSession`.
List methods return `(items, total)` so the service can page without a second round trip; a
read-then-write path gets an explicit `_for_update` variant; input normalization helpers such
as `normalize_email` live beside the repository that depends on them.

**Correct:**

```python
async def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
    total = await self._session.scalar(select(func.count()).select_from(User))
    rows = await self._session.scalars(
        select(User).order_by(User.created_at, User.id).offset(offset).limit(limit)
    )
    return list(rows.all()), total or 0
```

Enforced by: scaffold: .agents/scaffold/backend_crud.py, review

### Take the request-scoped session; never build an engine in a repository

One `AsyncSession` per request, handed down from `SessionDep`. A repository that calls
`create_async_engine` opens a second connection pool outside the request's transaction, so its
writes commit independently of everything else in the same request.

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Commit only through `app/core/transactions.py`

`transaction(session)` joins an in-flight transaction or opens one, committing on success and
rolling back on any exception. It is the single place `commit()` and `rollback()` are called,
which is what makes "did this service commit?" a testable assertion on a fake session.

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Use SQLAlchemy, never SQLModel

The packaged FastAPI skill prefers SQLModel; this repo does not. SQLModel collapses the API
schema and the table into one class, which breaks the `XRead`/`XCreate` split, the
`from_attributes` boundary, and the rule that a model never imports upward.

Enforced by: review
