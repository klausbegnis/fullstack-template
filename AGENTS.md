# AGENTS.md — fullstack-template

Fullstack template (FastAPI backend + Next.js frontend) with one worked domain — auth + users —
built to be extended by agents. This file states only what an agent would get wrong unguided.

## Tech stack — exact resolved versions (do not assume a newer/older API)

| Backend | Version | Frontend | Version |
|---|---|---|---|
| Python | 3.12 | Next.js | 16.3.5 (Turbopack) |
| FastAPI | 0.141.1 | React / react-dom | 19.2.0 |
| SQLAlchemy (async) | 2.0.54 | TypeScript (strict) | 5.9.3 |
| asyncpg | 0.31.0 | Tailwind CSS | 4.1.11 (CSS-first, no `tailwind.config.*`) |
| Alembic | 1.20.0 | @tanstack/react-query | 5.103.1 |
| pydantic / pydantic-settings | 2.13.5 / 2.15.0 | zustand | 5.0.11 |
| PyJWT | 2.14.0 | react-hook-form / zod / @hookform/resolvers | 7.88.0 / 4.6.5 / 5.9.1 |
| argon2-cffi | 25.1.0 | orval | 8.34.0 |
| uvicorn | 0.53.0 | vitest / @vitest/coverage-v8 | 4.1.11 |
| ruff | 0.16.8 | eslint / eslint-config-next | 9.39.5 / 16.3.5 |
| mypy (strict) | 2.3.1 | eslint-plugin-boundaries | 7.2.0 |
| pytest | 9.1.1 | eslint-plugin-use-client | 1.2.0 |
| PostgreSQL | 16 | prettier | 3.5.3 |
| — | — | Node.js | 22 (pinned in `frontend/.nvmrc` and `package.json` `engines.node`; CI uses 22) |

Backend uses `uv`; frontend uses `npm` (`package-lock.json` committed). eslint is pinned to
`9.39.5` exactly — `eslint-config-next@16.3.5` breaks on ESLint 10.

## Backend layering — enforced by AST tests, not convention

`router -> service -> repository -> model`. `tests/unit/architecture/*_boundaries.py` AST-parses
routers and fails the build on a violation; add a matching `test_<feature>_boundaries.py` for any
new router.

- **router**: HTTP only. Must not import `app.repositories`, `app.models`, `sqlalchemy`, or
  `app.core.database`.
- **service**: owns domain validation, RBAC, and the transaction boundary. Must not import `fastapi`. Every mutation
  runs inside `async with transaction(self._session):` from `app/core/transactions.py` — never a bespoke
  `@asynccontextmanager` or a bare `.commit()`. This repo used to duplicate that helper across services; do not
  reintroduce it.
- **repository**: constructor takes `session: AsyncSession`; calls `.flush()` only, never
  `.commit()`; raises no `APIException`.
- **model**: SQLAlchemy 2.0 declarative, `Mapped[...]`, never imports upward. Every table pins
  `__table_args__ = {"schema": ...}` — schema-per-bounded-context (`app/models/db_schemas.py`
  currently defines `infra` and `iam`). New models register by import side effect in
  `app/models/__init__.py`.
- **app/dependencies/**: the only layer importing both `Depends` and service+repository classes.
  One `get_<x>_service` + `XServiceDep = Annotated[XService, Depends(get_<x>_service)]` per
  feature, re-exported from `app/dependencies/__init__.py`. Service `__init__` must have **no
  defaulted parameters** (asserted by `test_user_service_dependency_is_non_optional_...`).
- List endpoints return `PaginatedResponse[T]`; single-item endpoints return `SuccessResponse[T]`.
  Domain errors are always `APIException` subclasses from `app/core/exceptions.py` — never a raw
  `HTTPException`.

## Frontend boundaries — enforced by eslint-plugin-boundaries

`app -> features -> components(ui) -> lib`. `lib` imports only `lib`. **No feature imports another feature.** Inside a
feature: `containers -> hooks -> api -> model`; `model` imports no `react`, `next`, or `@tanstack/*` (plain
types/zod/pure functions — see `features/users/model/`). Configured in `frontend/eslint.config.mjs`; it silently
reports nothing if `import/resolver` is ever removed from that config — verify with a planted violation if you touch
it. No barrel (`index.ts` re-export) files anywhere under `src/` except the generated client.

## No inline comments — enforced on both stacks

- Frontend: `local/no-comments-except-tsdoc` (`frontend/tools/eslint/no-comments-except-tsdoc.cjs`)
  is wired into `eslint.config.mjs` and fails `npm run lint` on any comment that is not a `/** */`
  TSDoc block directly above an exported declaration.
- Backend: docstrings only, no inline `#` comments explaining code. Ruff does **not** enforce
  this, but `backend/tests/unit/architecture/test_no_comments.py` does: it tokenizes every `.py`
  file under `app/`, `alembic/` and `tests/` and fails on any comment that isn't a functional
  directive (`# noqa`, `# type:`, `# pragma:`, `# ruff:`, `# mypy:`, `#!`). It runs as part of
  `pytest`, so it is covered by CI and the pre-commit hook's unit-test run.

## Server vs. client components

Rule of thumb, not "container/presentational": **code crosses through imports, data crosses
through props.** `'use client'` only where a client-only feature (state, effects, event handlers,
browser APIs) is genuinely used; `eslint-plugin-use-client` fails on both a missing directive and
an unnecessary one. **Files under `features/*/components/` carry no `'use client'` and still
render on the server** — they are props-only views, not "presentational-therefore-client".
`containers/` is where the client boundary and hooks legitimately live.

## Auth

httpOnly cookies only — `app_access`, `app_refresh` (path `/api/auth`), and a **readable**
`app_csrf` used for double-submit CSRF on mutating requests. **Never `localStorage` /
`sessionStorage`** for tokens (XSS-prone, and blocks RSC from reading auth state).
`frontend/src/middleware.ts` does a cheap cookie-presence redirect only — **it is not the
authorization boundary** (CVE-2025-29927: middleware can be bypassed; Next.js 16.3+ also deprecates
this file convention in favor of `proxy.ts` — same security point either way). The real gate is
`frontend/src/lib/auth/dal.ts` (`import "server-only"`, wrapped in React `cache()`) — every
protected route/layout/Server Action must call `requireUser()`/`getCurrentUser()` from there.

## Environment variables — required before anything runs

`backend/.env.example` is the reference for every setting; copy it to `backend/.env` before
running anything backend-related.

- **`DATABASE_URL`** — no working default; `postgresql+asyncpg://user:pass@host:port/db`. Required
  by `uv run python main.py`, `alembic upgrade head`/`check`, and the integration test tier — all
  three hard-crash with an unhandled pydantic `ValidationError` (not a friendly message) if unset.
- **`AUTH_JWT_SECRET`** — required, >= 32 bytes, **no default anywhere**: a bare local run fails
  closed and `docker-compose.yml` (`${AUTH_JWT_SECRET:?...}`) refuses to start. By design — a
  template must never ship a working signing key. Tests are the sole exception (`TESTING=true`
  injects a fixed test-only key). Generate:
  `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

Local example (from `backend/`): `cp .env.example .env && echo
'DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app' >> .env`.

**Quickstart — Docker Compose** (repo root, `docker-compose.yml`: `db`/`api`/`frontend` services):
`AUTH_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") docker compose
up --build` — the `api` container runs `alembic upgrade head` on start.

## Commands (all verified against this checkout)

Backend, from `backend/`:

| Task | Command |
|---|---|
| Install | `uv sync` |
| Run dev server | `uv run python main.py` (needs `DATABASE_URL`, see above) |
| Test | `uv run pytest` — **130 passed, 24 skipped** without `DATABASE_URL` (integration tier silently skipped); **154 passed** with it. A green run without `DATABASE_URL` is not full coverage. |
| Lint | `uv run ruff check .` |
| Format check / write | `uv run ruff format --check .` / `uv run ruff format .` |
| Typecheck | `uv run mypy app` |
| Apply migrations | `uv run alembic upgrade head` (needs a reachable `DATABASE_URL`, see above) |
| Check migrations vs. models | `uv run alembic check` (same precondition) |
| Create a migration (recommended) | `uv run python -m app.commands.create_migration -m "<msg>"` (`--empty` for no autogenerated body) — runs `alembic revision --autogenerate`, strips the banner comments Alembic injects, then runs `ruff check --fix`/`ruff format` so the output is compliant with no manual cleanup. |
| Create a migration (raw) | `uv run alembic revision --autogenerate -m "<msg>"` — works, but leaves `# ### commands auto generated ... ###` banner comments in the file that must be removed by hand to satisfy the no-comments rule. |
| Export OpenAPI schema | `uv run python -m app.commands.export_openapi` (writes `backend/openapi.json`, no DB needed) |

Frontend, from `frontend/`:

| Task | Command |
|---|---|
| Install | `npm ci` |
| Regenerate API client (orval, reads `../backend/openapi.json`) | `npm run generate:api` |
| Run dev server | `npm run dev` |
| Build | `npm run build` |
| Lint | `npm run lint` |
| Typecheck | `npm run typecheck` |
| Format check / write | `npm run format` / `npm run format:write` |
| Test (with coverage) | `npm run test` |
| Test (fast, no coverage) | `npm run test:fast` |

`typecheck`/`test`/`build` each run `generate:api` first via `pretypecheck`/`pretest`/`prebuild`
npm hooks — **`lint` does not**: there is no `prelint` script, and `npm run lint` (plain
`eslint .`) passes even with `src/lib/api/generated/` deleted. `next lint` was removed in Next 16
— CI calls `eslint` directly.
`.githooks/pre-commit` is opt-in per clone (`git config core.hooksPath .githooks`) and is
change-scoped: staged `backend/` paths run `ruff format --check`/`ruff check`/`pytest
tests/unit`; staged `frontend/` paths run `format`/`lint`/`test:fast`; an untouched stack is
skipped. It deliberately excludes mypy, DB-backed integration tests, `typecheck`, and `build` —
those run in CI only.

## Adding things — mechanical recipes

**Backend endpoint** (existing entity): add a handler in `app/routers/<x>.py` using the existing
`XServiceDep`; wire an auth dependency (`RequireAdmin` / `SelfOrAdmin` / `CurrentUser`) as an
explicit parameter; return `SuccessResponse[T]` (single item) or `PaginatedResponse[T]` (list).
Reference: `app/routers/users.py`.
**Backend entity + migration**: model in `app/models/<x>.py` (import it in `app/models/__init__.py`) -> repository
`app/repositories/<x>.py` (session ctor, `.flush()` only) -> service `app/services/<x>.py` (transaction boundary via
`transaction()`) -> router + Pydantic schemas -> `app/dependencies/<x>.py` (`get_<x>_service`/`XServiceDep`,
re-exported from `app/dependencies/__init__.py`) -> `tests/unit/architecture/test_<x>_boundaries.py` (model on
`test_user_boundaries.py`) -> `uv run python -m app.commands.create_migration -m "add <x>"` -> `uv run alembic upgrade
head` -> `uv run alembic check`. Reference vertical: `app/{models,repositories,services,routers,schemas}/user*.py`.
**Frontend feature**: create `src/features/<f>/{model,api,hooks,containers,components,server}`. `model` =
types/zod/pure functions only. `api` = TanStack Query hooks over the orval-generated client plus a mapper that unwraps
the envelope and converts `snake_case` (see `features/users/api/user-mapper.ts`). `server` = an RSC fetch helper for
the initial page load (see `features/users/server/fetch-users-page.ts`). `components` = props-only views, no `'use
client'`. `containers` = the client boundary, hooks, mutations. Wire a route under `src/app/(app)/<f>/`.
**Frontend form**: zod schema in `features/<f>/model`; `useForm<z.input<S>, unknown,
z.output<S>>` + `zodResolver` (the two-type-param form is mandatory under strict TS or
`handleSubmit` mistypes); submit through `useMutation`, not a raw `<form action>` — React 19
Actions are reserved for setting/clearing the httpOnly session cookie only (login/logout).
Reference: `features/users/containers/create-user-form.tsx`.

## Skills and agents (`.claude/`)

| Path | Purpose |
|---|---|
| `.claude/skills/task/SKILL.md` | `/task <description> [--gate=manual\|auto]` — two-gate pipeline (plan/implement/review, then isolated QA) from a worktree to a ready-for-review PR. |
| `.claude/skills/orchestrate/SKILL.md` | `/orchestrate <items>` — runs a backlog of `/task` items concurrently with a bounded worker pool and per-task isolation. |
| `.claude/agents/backend-reviewer.md` | Reviews a backend diff/branch against the layering, migration, DI, auth, and error-contract rules above; runs ruff/mypy/alembic/pytest as evidence. |
| `.claude/agents/frontend-reviewer.md` | Reviews a frontend diff/branch against import boundaries, server/client rules, auth, and forms; runs lint/typecheck/format/test/build. |
| `.claude/agents/uncle-bob.md` | Clean-code review — naming, function size, duplication, and enforcement of the no-comments rule — across both stacks. |

**Non-Claude agents (e.g. Codex):** these live under `.claude/skills/` and `.claude/agents/` in
this repo, not the `.agents/skills/` path some tools look for by convention. This `AGENTS.md` is
the canonical, tool-agnostic entry point regardless of where an agent expects skills to live.

## `next dev` will generate its own AGENTS.md/CLAUDE.md inside `frontend/`

Next.js 16.3+ writes `frontend/AGENTS.md` and `frontend/CLAUDE.md` (`@AGENTS.md`) the first time
`next dev` runs, and owns everything between `<!-- BEGIN:nextjs-agent-rules -->` and
`<!-- END:nextjs-agent-rules -->` in that file — it will rewrite that block on every `next dev`
start. **This root `AGENTS.md` is the canonical one for the whole repo** and is untouched by that
mechanism; never move rules from here into `frontend/AGENTS.md`'s managed block.
