# backend — FastAPI service

Python 3.12 + FastAPI + async SQLAlchemy over PostgreSQL, laid out layer-first:
`app/{routers,services,repositories,models,schemas/api,dependencies,core,config,commands}`,
Alembic revisions in `alembic/versions/`, tests split into `tests/unit` and `tests/integration`.
The repo-wide guide is the root [`AGENTS.md`](../AGENTS.md); the reasoning behind the layering is
in [`docs/architecture/backend.md`](../docs/architecture/backend.md).

## Read before editing

| Rule file                                                                         | Applies to                                                                                                   |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| [`.agents/rules/backend/layering.md`](../.agents/rules/backend/layering.md)       | `backend/app/**`                                                                                             |
| [`.agents/rules/backend/persistence.md`](../.agents/rules/backend/persistence.md) | `backend/app/models/**`, `backend/app/repositories/**`, `backend/alembic/**`                                 |
| [`.agents/rules/backend/api-crud.md`](../.agents/rules/backend/api-crud.md)       | `backend/app/routers/**`, `backend/app/schemas/**`, `backend/app/services/**`, `backend/app/dependencies/**` |
| [`.agents/rules/backend/testing.md`](../.agents/rules/backend/testing.md)         | `backend/tests/**`                                                                                           |

## Checks

Run from `backend/`. `DATABASE_URL` and `AUTH_JWT_SECRET` must be set first — see
`.env.example`.

| Task          | Command                                                                                                              |
| ------------- | -------------------------------------------------------------------------------------------------------------------- |
| Lint / format | `uv run ruff check .` · `uv run ruff format --check .`                                                               |
| Typecheck     | `uv run mypy app`                                                                                                    |
| Test          | `uv run pytest` (integration tier is skipped without `DATABASE_URL`)                                                 |
| Migrations    | `uv run python -m app.commands.create_migration -m "<msg>"` · `uv run alembic upgrade head` · `uv run alembic check` |
| API contract  | `uv run python -m app.commands.export_openapi`                                                                       |

## Code Review Rules

### Layering

- A router must not import `app.repositories`, `app.models`, `sqlalchemy` or `app.core.database`. Safe path: call one method on the injected `XServiceDep` and return the envelope.
- A service must not import `fastapi`. Safe path: raise an `APIException` subclass; the handlers in `main.py` turn it into a response.

### Transactions

- Do not commit in a repository. Safe path: `await self._session.flush()`; the service's `async with transaction(self._session):` commits.
- Do not write a bespoke transaction context manager. Safe path: `transaction()` from `app/core/transactions.py` is the only one.

### Routes

- Do not add a route without an auth dependency unless it is `/`, `/health`, `/auth/login` or `/auth/refresh`. Safe path: an explicit `RequireAdmin`, `SelfOrAdmin` or `CurrentUser` parameter.
- Do not raise `HTTPException` or return a bare payload. Safe path: an `APIException` subclass, and `-> SuccessResponse[T]` or `-> PaginatedResponse[T]` as the return annotation.
- Do not rename a route handler casually: FastAPI derives `operationId` from the handler name and the orval client is named from it. Safe path: rename only together with `export_openapi`, `npm run generate:api` and the frontend caller fixes in the same PR.

### Persistence

- Do not add a table without a schema from `DOMAIN_SCHEMAS`. Safe path: `__table_args__ = (..., {"schema": "iam"})`, adding the schema to `app/models/db_schemas.py` first.
- Do not edit an Alembic revision that already exists on `origin/main`. Safe path: a new revision from `python -m app.commands.create_migration`.

### Tests

- Do not use `unittest.mock` under `tests/unit`. Safe path: the fakes in `tests/support/fakes.py`.
- Do not report `pytest` as green without `DATABASE_URL`. Safe path: say the integration tier was skipped, or run it with a database.
