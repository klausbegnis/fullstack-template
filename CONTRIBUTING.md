# Contributing

This standard applies equally to a human contributor and an agent (Claude Code, Codex, or
otherwise). `/task` automates the full workflow below end to end; a human doing it by hand follows
the same steps in the same order.

## Workflow

1. **Issue first.** No PR without an issue. Pick the matching issue form (`feature`, `bug`,
   `chore`, `spike`, or `support`) and fill in every required field.
2. **`agent-ready`.** An issue gets the `agent-ready` label only when its `Specs` and `Acceptance
   criteria` sections are complete enough that an unattended agent needs no clarification to start
   work. A human triager or the issue author applies it — never the implementing agent itself,
   since that would be grading its own homework. An issue without it is not picked up by `/task`
   unattended.
3. **Branch.** Cut a branch named `<type>/<issue-number>-<kebab-slug>`, e.g.
   `feat/42-refresh-token-rotation`. Types: `feat`, `fix`, `chore`, `docs`, `spike`.
4. **Draft PR.** Open the PR as a draft as soon as there is a commit worth showing. Reference the
   issue with `Closes #<number>`.
5. **Review.** Address feedback with new commits, not force-pushed rewrites, until the reviewers
   (see below) and CI are satisfied.
6. **Ready for review -> merge.** Mark the PR ready once checks are green and the Definition of
   Done is met. Merge after approval.

## Labels

Every issue carries exactly one `type/*`, at least one `area/*`, and any number of flow labels.

Area:

| name | description |
|---|---|
| backend | FastAPI, SQLAlchemy, Alembic, backend tests |
| frontend | Next.js, React, TypeScript, frontend tests |
| full-stack | Spans backend and frontend in one change |
| devops | CI, Docker, tooling, hooks, release plumbing |
| security | Authentication, authorisation, secrets, dependency risk |

Type:

| name | description |
|---|---|
| bug | Behaviour that contradicts the stated specification |
| feature | New capability that does not exist yet |
| chore | Maintenance with no behaviour change |
| spike | Time-boxed investigation that produces a document, not a feature |
| docs | Documentation only |
| support | A question or a request for help, not a code change |

Flow:

| name | description |
|---|---|
| needs-triage | Not yet specified well enough to start |
| agent-ready | Specification is complete enough for an unattended agent |
| blocked | Waiting on another issue, a decision, or an external party |

## Commits

Conventional Commits, imperative mood: `feat: add refresh token rotation`, `fix: reject expired
CSRF token`. The body explains **why**, not what the diff already shows. Do not squash a branch's
history into a single meaningless `wip` or `fixes` commit before merge — keep commits that each
carry a real reason for existing.

## Code rules

The canonical source is [`AGENTS.md`](./AGENTS.md); it is not restated here. Non-negotiable, both
stacks:

- No inline comments explaining code, in any language. Docstrings/TSDoc on definitions only.
  Enforced by `backend/tests/unit/architecture/test_no_comments.py` and the frontend
  `local/no-comments-except-tsdoc` ESLint rule.
- Backend layering (`router -> service -> repository -> model`) is enforced by AST-based
  architecture tests under `backend/tests/unit/architecture/`, not by convention.
- Frontend boundaries (`app -> features -> components(ui) -> lib`, no feature importing another
  feature) are enforced by `eslint-plugin-boundaries` in `frontend/eslint.config.mjs`.
- English only, everywhere: code, comments where they are permitted at all, commit messages,
  issues, PRs.

## Local setup

Backend, from `backend/` (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
cp .env.example .env
```

Set `DATABASE_URL` (a reachable PostgreSQL 16) and `AUTH_JWT_SECRET` (>=32 bytes) in `.env` —
neither has a working default; see `AGENTS.md`.

Frontend, from `frontend/` (Node 22):

```bash
npm ci
cp .env.example .env.local
```

## Checks

Backend, from `backend/`:

| Check | Command |
|---|---|
| Format | `uv run ruff format --check .` |
| Lint | `uv run ruff check .` |
| Typecheck | `uv run mypy app` |
| Migrations vs. models | `uv run alembic upgrade head && uv run alembic check` (needs `DATABASE_URL`) |
| Tests | `uv run pytest -n 4` (see the warning below) |

Frontend, from `frontend/`:

| Check | Command |
|---|---|
| Lint | `npm run lint` |
| Typecheck | `npm run typecheck` |
| Format | `npm run format` |
| Tests | `npm run test` |
| Build | `npm run build` |

## `pytest` without `DATABASE_URL` lies to you

**Running `uv run pytest` with no `DATABASE_URL` set reports green while silently skipping the
entire integration tier.** In this checkout that is the difference between:

| `DATABASE_URL` | Result | What actually ran |
|---|---|---|
| unset | `180 passed, 24 skipped` | unit tier only; exit code 0 |
| set to a reachable Postgres 16 | `204 passed` | unit tier plus the 24 integration tests |

The absolute totals move every time someone adds a test. The gap does not: those 24 tests are
the only ones that exercise a real database, a real session, and the real error contract.

A skip is not a pass. Before opening or approving a PR that touches `backend/`, run the full
suite against a real database:

```bash
export DATABASE_URL="postgresql+asyncpg://app:app@localhost:5432/app"
export AUTH_JWT_SECRET="local-verification-insecure-secret-32bytes"
uv run alembic upgrade head
uv run pytest -n 4
```

`-n 4` runs the suite on four pytest-xdist workers. Each worker creates its own migrated database
on the same server (`<database>_<worker>_<run>`, see `tests/support/worker_database.py`) and drops
it when it finishes, so workers never see each other's rows. Migration tests that downgrade work on
scratch databases cloned per test (`tests/support/scratch_database.py`). Without `-n` the suite
runs serially against `DATABASE_URL` itself.

If the output says `skipped` and you have not set `DATABASE_URL`, you have not run the tests —
you have run a subset that happens to exit 0.

## Pre-commit hook

`.githooks/pre-commit` is change-scoped and fast: it inspects staged paths and only checks the
stack that changed, and it runs no test suite. On staged `backend/` files it runs
`ruff format --check` and `ruff check`. On staged `frontend/` files it first refuses a `node` whose
major differs from `frontend/.nvmrc` (`task_env.py node`), then runs Prettier and ESLint on the
staged frontend files only. On staged `.github/`, `.claude/`, `.agents/`, `.codex/`, `docs/prds/` or `scripts/`
files it runs the harness contract tests, the task-environment tests and the hook tests. An untouched stack is skipped entirely. It does not run mypy,
`typecheck`, the test suites or `build` — those are the task gates' and CI's job.

Install it per clone:

```bash
git config core.hooksPath .githooks
```

`--no-verify` is not acceptable on a PR branch. If the hook is blocking you, fix what it caught —
do not bypass it.

## Definition of Done

- [ ] Issue exists and the PR references it with `Closes #<number>`.
- [ ] Backend checks pass: format, lint, mypy, `alembic check`, and `pytest` run **with**
      `DATABASE_URL` set.
- [ ] Frontend checks pass: lint, typecheck, format, test, build.
- [ ] No inline comments added.
- [ ] `backend/openapi.json` regenerated and committed if the API contract changed, and
      `frontend/src/lib/api/generated/**` regenerated to match.
- [ ] New/changed models have an accompanying Alembic migration; `alembic check` is clean.
- [ ] The architecture tests under `backend/tests/unit/architecture/` and the frontend
      `src/testing/architecture.node.test.ts` pass; they discover new routers, services, features
      and pages automatically, so a new slice needs tests but no new architecture test.
- [ ] The path-scoped rules in `.agents/rules/` for every touched path are satisfied (each rule
      names the check that enforces it).
- [ ] CI is green.

## Review

Three read-only review agents, maintained in `.agents/agents/` and exposed to Claude Code via
`.claude/agents/` and to Codex via `.codex/agents/`, cover a PR's diff:

- `backend-reviewer` — layering, migrations, DI, auth, error contract.
- `frontend-reviewer` — import boundaries, server/client rules, auth, forms.
- `uncle-bob` — naming, function size, duplication, the no-comments rule, across both stacks.

A PR merges when these reviews are satisfied, a human has approved, and CI (`.github/workflows/
ci.yml`) is green. CI running the backend job with `DATABASE_URL` set is what runs the full test
suite the local hook does not — do not treat a green pre-commit hook as equivalent to a green CI
run.
