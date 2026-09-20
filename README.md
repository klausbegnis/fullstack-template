# fullstack-template

A fullstack template: a FastAPI backend and a Next.js frontend, wired together with one worked
domain — **authentication and user management** — and nothing else. It exists to be extended: the
auth + users vertical is the reference pattern for every layer, and the repo ships lint rules,
AST-based architecture tests, and a set of agent skills/reviewers that hold new code to the same
shape.

**Scope, honestly**: there is no billing, no tenancy, no catalog, no second domain. If you need a
"real" business entity to copy from, copy the `users` vertical (backend) and the `features/users`
vertical (frontend) — see the recipes in [`AGENTS.md`](./AGENTS.md).

## What's in the box

| | |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic + PostgreSQL 16, Argon2id password hashing, JWT access tokens + rotating opaque refresh tokens, double-submit CSRF, RBAC (admin/member) |
| Frontend | Next.js 16.3.5 (App Router, RSC-first) + React 19 + TypeScript (strict) + Tailwind CSS 4 + TanStack Query + react-hook-form/zod, an orval-generated API client |
| Agent tooling | Claude and Codex skills for grooming, delivery, and orchestration, plus three shared review rubrics — see below |

## Quickstart — Docker Compose

Requires Docker with Compose v2+. From the repo root:

```bash
AUTH_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") docker compose up --build
```

`AUTH_JWT_SECRET` is **required** — Compose refuses to start the `api` service without it
(`docker compose config` fails fast with `required variable AUTH_JWT_SECRET is missing a value`),
and it must decode to at least 32 bytes. Export it in your shell or put it in a root `.env` file
that Compose reads automatically; do not commit it.

This brings up Postgres 16, the API (migrated automatically on container start via
`backend/entrypoint.sh`, which runs `alembic upgrade head` before serving), and the frontend,
proxying `/api/*` from the frontend to the API container. Frontend: http://localhost:3000. API:
http://localhost:8000.

## Quickstart — local development

Backend (from `backend/`, requires Python 3.12 and [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python main.py
```

`.env.example` sets `DATABASE_URL` to `postgresql+asyncpg://backend:backend@localhost:5432/backend`
— point it at a real reachable Postgres 16 (e.g. `docker compose up db`, or edit the URL) before
running the commands above; without it, both `alembic upgrade head` and `main.py` crash with a
pydantic `ValidationError`. `AUTH_JWT_SECRET` is required and has no default — set it to at least 32
bytes before anything will start. Generate one with
`python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

Frontend (from `frontend/`, requires Node 22+; needs `backend/openapi.json` present, which is
committed):

```bash
npm ci
cp .env.example .env.local
npm run dev
```

## Tests and checks

| | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| Test | `uv run pytest` | `npm run test` |
| Lint | `uv run ruff check .` | `npm run lint` |
| Format check | `uv run ruff format --check .` | `npm run format` |
| Typecheck | `uv run mypy app` | `npm run typecheck` |
| Build/verify | `uv run alembic check` | `npm run build` |

All of the above were run against this repository and passed: **204 backend tests** (with
`DATABASE_URL` set — without it, 24 integration tests skip silently and the suite still exits 0,
see [`CONTRIBUTING.md`](./CONTRIBUTING.md)), **50 frontend tests**, clean
ruff/mypy/eslint/tsc/prettier, and a clean `next build`. `.githooks/pre-commit` (enable with
`git config core.hooksPath .githooks`) runs a fast, change-scoped subset of these on staged files
before every commit.

## Architecture

Backend: `router -> service -> repository -> model`, with the transaction boundary centralized in
`app/core/transactions.py` and enforced by AST-parsing architecture tests. Frontend:
`app -> features -> components/ui -> lib`, enforced by `eslint-plugin-boundaries`, with a strict
server/client split (RSC by default; `'use client'` only where genuinely needed).

Full write-ups, including the response envelopes, the error contract, the schema-per-bounded-
context Alembic setup, and the enforcement mechanisms themselves:

- [`docs/architecture/backend.md`](./docs/architecture/backend.md)
- [`docs/architecture/frontend.md`](./docs/architecture/frontend.md)
- [`docs/development/backend.md`](./docs/development/backend.md) — PR checklist
- [`docs/development/frontend.md`](./docs/development/frontend.md) — PR checklist

Agent-facing rules (the things an agent would get wrong without being told — exact versions,
layering rules, auth gotchas, exact commands) live in [`AGENTS.md`](./AGENTS.md), which is the
canonical doc for both Claude Code (`CLAUDE.md` is a one-line pointer to it) and any other coding
agent.

## Agent tooling

This template ships a small pipeline for agent-driven development. Claude discovers
skills under `.claude/skills/` with `/name` commands; Codex discovers corresponding
skills under `.agents/skills/` with `$name` commands. Codex reviewer agents live in
`.codex/agents/` and read the maintained rubrics in `.claude/agents/`.

| Claude / Codex | Purpose |
|---|---|
| `/groom <idea>` / `$groom <idea>` | Turns a product idea into a reviewed PRD under `docs/prds/` and the GitHub issues that implement it. |
| `/task #123` / `$task #123` | Takes one issue through a worktree, implementation, checks, review, QA, and a PR. |
| `/orchestrate --label backend` / `$orchestrate --label backend` | Runs an eligible backlog with bounded concurrency, dependency ordering, and per-task isolation. |
| `backend-reviewer` agent | Reviews a backend diff against the layering, migration, DI, auth, and error-contract rules, running the real checks as evidence. |
| `frontend-reviewer` agent | Reviews a frontend diff against import boundaries, server/client rules, auth, and forms, running the real checks as evidence. |
| `uncle-bob` agent | Clean-code/design review — naming, function size, duplication, and the no-comments rule — across both stacks. |

`AGENTS.md` is the shared project guide, and `CLAUDE.md` points to it. The Claude
workflow files hold the detailed repository contracts; Codex skills are short
adapters for their host-specific commands. Review criteria stay in the Claude
Markdown rubrics and are loaded by the Codex reviewer agents at review time.
Update a shared rule in its maintained file, then check whether the small Codex
adapter needs a matching change. Run the agent contract tests after either side
changes.

The loop is `idea -> PRD -> issues -> PRs`. A PRD in `docs/prds/` holds the reasoning and is
reviewed as a diff like any other file; a GitHub issue holds one mergeable unit of work and closes
with its PR. The issue forms in `.github/ISSUE_TEMPLATE/` are not decoration — `/task` parses
their sections, and a test fails if a form and the parser ever disagree.

Start here:

```bash
git config core.hooksPath .githooks
scripts/sync-labels.sh
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the contribution standards that apply to humans and
agents alike, [`docs/prds/README.md`](./docs/prds/README.md) for why PRDs are files and not
issues, and [`AGENTS.md`](./AGENTS.md) for the full index, exact commands, and mechanical recipes
for extending either stack.
