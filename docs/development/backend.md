# Backend PR checklist

The checklist that used to live here is now enforced code and path-scoped rules, so it cannot
drift from what CI checks:

- **What to satisfy** — the rule files under [`.agents/rules/backend/`](../../.agents/rules/backend/)
  (`layering.md`, `persistence.md`, `api-crud.md`, `testing.md`). Each rule names the test, lint
  rule or hook that enforces it. Claude Code loads them when you touch matching files; Codex reads
  them from the index in [`backend/AGENTS.md`](../../backend/AGENTS.md).
- **What to run** — the command table in [`backend/AGENTS.md`](../../backend/AGENTS.md): format,
  lint, mypy, `alembic upgrade head` + `alembic check`, `pytest` **with** `DATABASE_URL` set, and
  `export_openapi` when the contract changed (CI fails on a stale `backend/openapi.json`).
- **What "done" means** — the Definition of Done in [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

Architecture reasoning stays in [`docs/architecture/backend.md`](../architecture/backend.md).
