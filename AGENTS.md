# AGENTS.md — fullstack-template

Fullstack template (FastAPI backend + Next.js frontend) with one worked domain — auth + users —
built to be extended by agents. This file holds only what every session needs on every turn.
Everything scoped to a part of the tree lives in `.agents/rules/` (see the Rules index) and loads
when you touch matching files. `CLAUDE.md` files are one line, `@AGENTS.md`, everywhere.

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
| — | — | Node.js | 22 (`frontend/.nvmrc`, `engines.node: 22.x` with `engine-strict`; CI uses 22) |

Backend uses `uv`; frontend uses `npm` (`package-lock.json` committed). eslint is pinned to
`9.39.5` exactly — `eslint-config-next@16.3.5` breaks on ESLint 10.

## Rules index — read the matching file before editing

Rules are enforced by tests, lint and hooks; each rule names its check. Claude Code loads them
automatically through the `.claude/rules` symlink when a matching file is read. Codex: read the
file yourself before editing (the PostToolUse hook also injects the matching rules after an edit).

| Rule file | Loads for |
|---|---|
| `.agents/rules/backend/layering.md` | `backend/app/**` — router → service → repository → model, DI aliases, envelopes, `APIException` only, `async def` everywhere |
| `.agents/rules/backend/persistence.md` | `backend/app/models/**`, `backend/app/repositories/**`, `backend/alembic/**` — schema pins, naming convention, `.flush()` only, migrations |
| `.agents/rules/backend/api-crud.md` | `backend/app/{routers,schemas,services,dependencies}/**` — the CRUD recipe: auth dep per route, return annotations, status codes, transaction boundary, contract sync |
| `.agents/rules/backend/testing.md` | `backend/tests/**` — two tiers, fakes over mocks, one test module per service and router |
| `.agents/rules/frontend/architecture.md` | `frontend/src/**` — dependency rule incl. intra-feature layers, no barrels, generated client behind a mapper |
| `.agents/rules/frontend/server-client.md` | `frontend/src/app/**`, `features/*/{server,actions}/**`, `lib/auth/**` — RSC by default, `server-only`, `requireUser()`, pages = prefetch + container |
| `.agents/rules/frontend/data-and-forms.md` | `features/*/{api,containers,hooks,model}/**` — TanStack Query factories, mutations, derived state, forms |
| `.agents/rules/frontend/ui-components.md` | `frontend/src/components/**`, `features/*/components/**` — props-only views, no `'use client'`, accessibility |
| `.agents/rules/frontend/testing.md` | `frontend/src/**/*.test.*`, `frontend/src/testing/**` — layer → test type, MSW only, role queries |
| `.agents/rules/e2e.md` | `e2e/**` — role locators, web-first waits, API seed, route manifest, compose `e2e` run |
| `.agents/rules/harness.md` | `.claude/**`, `.agents/**`, `.codex/**`, `.github/**`, `docs/prds/**` — issue/PRD contract, single-source layout |

Nested guides `backend/AGENTS.md` and `frontend/AGENTS.md` repeat their side's index and carry
the `## Code Review Rules` Codex applies per changed file in PR review.

## Always-on rules (they fail dangerously if missed)

- **Layering is tested, not conventional.** `backend/tests/unit/architecture/` AST-parses every
  router, service, repository and model; `frontend/eslint.config.mjs` (`eslint-plugin-boundaries`)
  enforces `app -> features -> components(ui) -> lib` and `containers -> hooks -> api -> model`
  inside a feature. Both are discovery-based: a new feature needs no new architecture test.
- **No inline comments on either stack.** Backend: docstrings only
  (`tests/unit/architecture/test_no_comments.py`). Frontend: only `/** */` TSDoc directly above an
  exported declaration (`local/no-comments-except-tsdoc`). Intent goes in names and structure.
- **Domain errors are `APIException` subclasses** from `app/core/exceptions.py`, never a raw
  `HTTPException`. Every mutation runs inside `async with transaction(self._session):` from
  `app/core/transactions.py`; nothing else commits.
- **Auth is httpOnly cookies only** — `app_access`, `app_refresh` (path `/api/auth`) and a readable
  `app_csrf` for double-submit CSRF. Never `localStorage`/`sessionStorage`. `frontend/src/middleware.ts`
  (`proxy.ts` in Next 16.3+) is a cookie-presence redirect, not the authorization boundary
  (CVE-2025-29927); the gate is `frontend/src/lib/auth/dal.ts` (`requireUser()`/`getCurrentUser()`).
  `/api/auth/renew` is a reserved Next Route Handler, not proxied to the API.
- **`'use client'` only where a client-only feature is genuinely used** — code crosses through
  imports, data crosses through props. `features/*/components/` render on the server.
- **Never edit a migration that is on `main`; never hand-edit `frontend/src/lib/api/generated/`.**
  The PreToolUse hook refuses both.
- **Never claim that a test, integration, recovery procedure, or external check passed unless it
  was actually run.** Quote the output.

## Environment variables — required before anything runs

`backend/.env.example` is the reference; copy it to `backend/.env` first.

- **`DATABASE_URL`** — no default; `postgresql+asyncpg://user:pass@host:port/db`. Required by
  `uv run python main.py`, `alembic upgrade head`/`check` and the integration test tier; all crash
  with an unhandled pydantic `ValidationError` if unset.
- **`AUTH_JWT_SECRET`** — required, >= 32 bytes, no default anywhere; `docker-compose.yml` refuses
  to start without it. Tests are the sole exception (`TESTING=true` injects a fixed key).
  Generate: `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

Quickstart (repo root): `AUTH_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
docker compose up --build` — the `api` container runs `alembic upgrade head` on start.

## Commands (verified against this checkout)

Backend, from `backend/`:

| Task | Command |
|---|---|
| Install | `uv sync` |
| Run dev server | `uv run python main.py` |
| Test | `uv run pytest -n 4` (one database per worker) — the integration tier is **silently skipped** without `DATABASE_URL`; a green run without it is not full coverage |
| Lint / format | `uv run ruff check .` · `uv run ruff format --check .` (`ruff format .` to write) |
| Typecheck | `uv run mypy app` |
| Migrations | `uv run alembic upgrade head` · `uv run alembic check` (both need a reachable `DATABASE_URL`) |
| Create a migration | `uv run python -m app.commands.create_migration -m "<msg>"` (`--empty` for no body) — strips Alembic's banner comments and formats the result |
| Export OpenAPI | `uv run python -m app.commands.export_openapi` (writes `backend/openapi.json`; CI fails if it is stale) |

Frontend, from `frontend/`:

| Task | Command |
|---|---|
| Install | `npm ci` |
| Regenerate API client (orval, reads `../backend/openapi.json`) | `npm run generate:api` |
| Run dev server | `npm run dev` |
| Build / Lint / Typecheck | `npm run build` · `npm run lint` · `npm run typecheck` |
| Format check / write | `npm run format` / `npm run format:write` |
| Test (coverage) / fast | `npm run test` / `npm run test:fast` |

`typecheck`/`test`/`build` run `generate:api` first; `lint` does not. `.githooks/pre-commit` is
opt-in per clone (`git config core.hooksPath .githooks`) and change-scoped; mypy, DB-backed tests,
`typecheck` and `build` run in CI only. Harness hooks: `.claude/settings.json` and
`.codex/hooks.json` both run the scripts in `.agents/hooks/` (Codex requires project trust and
`/hooks` approval per clone).

## Adding things

- **Backend CRUD or frontend feature:** run the `scaffold-crud` skill. It plans the artifact list,
  waits for approval, generates the whole slice from rule-compliant templates
  (`.agents/scaffold/`), then runs migration, OpenAPI export and client regeneration. Domain logic
  is the only hand-written part. Reference vertical: `app/**/user*.py`, `features/users/`.
- **Anything else:** the matching rule file is the recipe; `docs/architecture/*.md` holds the why.

## Work comes from issues, context comes from PRDs

| | PRD (`docs/prds/<NNNN>-<slug>.md`) | Issue (GitHub) |
|---|---|---|
| Answers | why, and what "done" means for a capability | what to build next, as one mergeable change |
| Lifetime / lives in | as long as the capability; the repo, reviewed as a diff | until the PR merges; the tracker |

An issue without a PRD is fine for a bug or a chore; a feature whose reasoning exists only in an
issue thread is not — a detached worktree cannot see that thread. `groom` writes the PRD and spawns
the issues; `task` consumes one issue. Both agree on the issue-body headings rendered by
`.github/ISSUE_TEMPLATE/*.yml` (`What is it`, `Specs`, `Pre-exploration`, `Acceptance criteria`,
`Out of scope`, `Related documents`, `Area`), enforced by
`backend/tests/unit/architecture/test_repo_contracts.py`. `Pre-exploration` is a head start, never
evidence: verify every path it hands you. Branch names, commit format, Definition of Done and labels
live in `CONTRIBUTING.md`.

## Skills and agents — one tree, two harnesses

Everything is maintained once under `.agents/`. Claude Code reaches it through the `.claude/rules`
and `.claude/skills` symlinks and thin `.claude/agents/*.md` frontmatter files; Codex reads
`.agents/skills/` natively and `.codex/agents/*.toml` point at the same rubric bodies. Skill and
agent bodies are tool-neutral, with a closing `## Harness notes` for the differences.

| Path | Purpose |
|---|---|
| `.agents/skills/groom/` | `groom <idea>` — idea → reviewed PRD → issues. The only skill that creates issues. |
| `.agents/skills/task/` | `task #123 \| <description> [--gate=manual\|auto]` — two-gate pipeline (plan/implement/review, then isolated QA) to a ready PR. |
| `.agents/skills/orchestrate/` | `orchestrate --label <l> \| <items>` — runs a backlog of `task` items concurrently with isolation. |
| `.agents/skills/scaffold-crud/` | generates a rule-compliant backend slice and/or frontend feature behind an approved artifact list. |
| `.agents/skills/verify-rules/` | plants known violations and reports which gate caught each; run after touching lint or architecture tests. |
| `.agents/skills/fastapi/`, `.agents/skills/react-best-practices/`, `.agents/skills/security-audit/` | vendored upstream skills (FastAPI's, from the installed package; Vercel's; Cloudflare's security audit, see `docs/development/security-audit.md`). Repo rules win on conflict. |
| `.agents/agents/{backend,frontend}-reviewer.md`, `uncle-bob.md` | read-only review rubrics (architecture per side; clean code across both). |

Invocation: `/name` in Claude Code, `$name` in Codex. Codex loads nested `AGENTS.md` only for the
directory it was launched in, so start it at the repo root.

## `next dev` generates `frontend/AGENTS.md`'s managed block

Next.js 16.3+ writes `frontend/CLAUDE.md` (`@AGENTS.md`) and owns everything between
`<!-- BEGIN:nextjs-agent-rules -->` and `<!-- END:nextjs-agent-rules -->` in `frontend/AGENTS.md`,
rewriting that block on every `next dev` start. Our content sits outside the block; never move
repo rules into it. This root file is canonical for the whole repo.
