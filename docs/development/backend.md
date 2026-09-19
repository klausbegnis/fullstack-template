# Backend PR checklist

Run everything below from `backend/`. Requires a PostgreSQL 16 database reachable at
`DATABASE_URL` and `AUTH_JWT_SECRET` (>=32 bytes) exported — e.g.:

```bash
export DATABASE_URL="postgresql+asyncpg://app:app@localhost:55432/app"
export AUTH_JWT_SECRET="local-verification-insecure-secret-32bytes"
```

## Before opening the PR

- [ ] `uv sync` — dependencies installed/up to date.
- [ ] `uv run ruff format --check .` — passes with no diff.
- [ ] `uv run ruff check .` — passes with no findings (includes mccabe `C90` and `PLR0915`
      size-limit rules — a function tripping these needs splitting, not a `noqa`).
- [ ] `uv run mypy app` — passes in strict mode.
- [ ] `uv run alembic upgrade head` then `uv run alembic check` — no drift between models and
      migration history. A new/changed model with no accompanying migration fails this step.
- [ ] `uv run pytest` — all tests pass, including the AST architecture tests under
      `tests/unit/architecture/`.
- [ ] No inline `#` comments explaining code — ruff does not catch this, but
      `tests/unit/architecture/test_no_comments.py` does (part of `uv run pytest` above).
      Docstrings on definitions are fine and expected.

## If the change touches persistence (new/changed model)

- [ ] The model pins `__table_args__ = {"schema": ...}` and the schema is listed in
      `app/models/db_schemas.py`.
- [ ] A new migration exists under `alembic/versions/` — never edit a migration that has already
      merged to `main`.
- [ ] A new enum column uses `sa.Enum(..., create_type=False)` plus an explicit
      `.create(op.get_bind(), checkfirst=True)` in `upgrade()` and `.drop(...)` in `downgrade()`.
- [ ] Migration created with `uv run python -m app.commands.create_migration -m "<msg>"`
      (preferred — auto-cleans banner comments and formats the result) or, if run raw via
      `alembic revision --autogenerate`, has its `# ### commands auto generated ... ###` banner
      comments removed by hand.

## If the change adds or touches a router

- [ ] The router imports none of `app.repositories`, `app.models`, `sqlalchemy`,
      `app.core.database`.
- [ ] Every endpoint has an explicit authorization dependency in its signature
      (`RequireAdmin`/`SelfOrAdmin`/`CurrentUser`, or a new equivalent) — not just a service
      dependency.
- [ ] A list endpoint returns `PaginatedResponse[T]`, never a bare `list[T]`.
- [ ] A `tests/unit/architecture/test_<feature>_boundaries.py` exists asserting the router has no
      forbidden imports and its service dependency is non-optional (model it on
      `test_user_boundaries.py`).
- [ ] Any raised domain error is an `APIException` subclass — no raw `HTTPException`.

## If the change adds or touches a service

- [ ] Every mutation runs inside `async with transaction(self._session):` from
      `app/core/transactions.py` — no bespoke transaction handling.
- [ ] The service does not import `fastapi`.
- [ ] `__init__` has no defaulted parameters.
- [ ] A self-service mutation (a user editing their own record) cannot escalate its own
      role/permissions — check against `app/services/users.py::update_user`'s guard.

## Before pushing

- [ ] `uv run python -m app.commands.export_openapi` and check whether `backend/openapi.json`
      changed — if it did, commit the updated file (the frontend's orval client is generated from
      it, and a stale `openapi.json` silently ships a stale frontend client).
- [ ] If `.githooks/pre-commit` is enabled (`git config core.hooksPath .githooks`), it already ran
      ruff format/check and `pytest tests/unit` on your staged files — do not bypass it with
      `--no-verify`.
