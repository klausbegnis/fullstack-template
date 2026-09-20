# Frontend PR checklist

The checklist that used to live here is now enforced code and path-scoped rules, so it cannot
drift from what CI checks:

- **What to satisfy** — the rule files under [`.agents/rules/frontend/`](../../.agents/rules/frontend/)
  (`architecture.md`, `server-client.md`, `data-and-forms.md`, `ui-components.md`, `testing.md`).
  Each rule names the eslint rule, architecture test or hook that enforces it. Claude Code loads
  them when you touch matching files; Codex reads them from the index in
  [`frontend/AGENTS.md`](../../frontend/AGENTS.md).
- **What to run** — the command table in [`frontend/AGENTS.md`](../../frontend/AGENTS.md):
  `generate:api` (after a backend contract change), `lint`, `typecheck`, `format`, `test`,
  `build`. Never commit `src/lib/api/generated/`.
- **What "done" means** — the Definition of Done in [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

Architecture reasoning stays in [`docs/architecture/frontend.md`](../architecture/frontend.md).
