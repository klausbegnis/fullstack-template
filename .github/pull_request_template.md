## What changed and why

<!-- Fill in before requesting review. -->

Closes #

## Verified

- [ ] Backend checks: `ruff format --check`, `ruff check`, `mypy app`, `alembic check`
- [ ] Frontend checks: `lint`, `typecheck`, `format`, `build`
- [ ] Full test suite run **with `DATABASE_URL` set** (`uv run pytest`, not just the default
      skipped run) and `npm run test`

## Screenshots

<!-- Required if this changes UI. Delete this section otherwise. -->

## Risk and rollback

<!-- What could break, and how to revert if it does. -->

## Checklist

- [ ] No inline comments added
- [ ] Docs updated (`AGENTS.md`, `docs/development/*`, or `docs/prds/*` as relevant)
- [ ] Migrations are reversible (`downgrade()` implemented and tested), or N/A
