---
name: scaffold-crud
description: Generate a complete CRUD vertical slice — FastAPI model/repository/service/schemas/router/dependencies plus both test tiers, and the Next.js feature with model/api/hooks/containers/components/server/testing and its route segment — from the templates in `.agents/scaffold/`, behind a frozen artifact list the user approves before anything is written. Use when the work is "add a new resource/entity/feature" and the structure should come from the templates rather than be improvised: the agent then edits only the domain decisions. Do NOT use it to change an existing slice, to add one endpoint to an existing router, or for anything that is not a new resource.
---

# scaffold-crud

Structure is not a design decision here — it is `.agents/rules/backend/*.md` and
`.agents/rules/frontend/*.md` rendered as files. This skill runs the two generators, gates them
on a user-approved artifact list, runs the checks, and hands back only the work that needs
judgement.

## 1. Gather the inputs

Ask for, or derive from the issue, and state them back before generating:

| Input | Shape | Notes |
|---|---|---|
| Entity | PascalCase singular (`Widget`) | drives class and schema names |
| Feature / tag | kebab-case plural (`widgets`) | **must equal** the backend router's plural stem, because the frontend templates derive the orval names from it |
| Bounded context | lower_snake schema (`inventory`) | must be in `DOMAIN_SCHEMAS`, or pass `--add-schema` |
| Fields | `name:str`, `quantity:int` (backend) · `name:string`, `quantity:number` (frontend) | `str/int/float/bool` · `string/number/boolean`; `--nullable <name>` per field |

`id`, `created_at`/`createdAt` and `updated_at`/`updatedAt` are in the templates — never pass them.

## 2. Plan, then freeze the list

```bash
python3 .agents/scaffold/backend_crud.py <Entity> --schema <ctx> [--add-schema] \
  --field <name>:<type> ... --plan
node .agents/scaffold/frontend_feature.mjs <feature> --entity <Entity> \
  --field <name>:<type> ... --plan
```

Each prints JSON: `artifacts`, the unified `diff` per patched file (backend only), an
`approved_list` and the `follow_up` commands. Show the two artifact lists and the patch diffs to
the user and **stop for approval**. On approval write each `approved_list` verbatim to a file —
that file is the contract; nothing outside it is written.

```bash
python3 -c "import json,sys;print('\n'.join(json.load(sys.stdin)['approved_list']))" \
  < plan-backend.json > approved-backend.txt
```

## 3. Apply

```bash
python3 .agents/scaffold/backend_crud.py <Entity> ... --apply --approved approved-backend.txt
node .agents/scaffold/frontend_feature.mjs <feature> ... --apply --approved approved-frontend.txt
```

Both call `.agents/scaffold/validate_scaffold.py` first: absolute paths, `..`, anything outside
the slice's directories and anything missing from the approved list are refused and nothing is
written. The backend apply also formats what it wrote with `ruff format` / `ruff check --fix`,
the frontend apply with `prettier --write`.

## 4. Migration and contract

In order, from `backend/`:

```bash
uv run python -m app.commands.create_migration -m "add <feature>"
uv run alembic upgrade head          # needs DATABASE_URL
uv run alembic check
uv run python -m app.commands.export_openapi
```

Then from `frontend/`: `npm run generate:api`. The generated client is named from FastAPI's
operation ids, which derive from the handler names — `listWidgetsWidgetsGet`,
`createWidgetWidgetsPost`, `getWidgetWidgetsWidgetIdGet`. The frontend templates already
reference those names; `npm run typecheck` is what proves they line up, so run it before
believing the slice compiles.

## 5. Run the check tables

| Backend, from `backend/` | Frontend, from `frontend/` |
|---|---|
| `uv run ruff format --check .` | `npm run format` |
| `uv run ruff check .` | `npm run lint` |
| `uv run mypy app` | `npm run typecheck` |
| `uv run pytest` (with `DATABASE_URL`) | `npm run test` |
| `uv run alembic check` | `npm run build` |

A `pytest` run without `DATABASE_URL` skips the whole integration tier, including the generated
`tests/integration/api/test_<feature>.py`; say so rather than reporting it green.

## 6. Hand the domain work to the implementer

The generated slice is deliberately generic. What the templates *decided* and the implementer
must now revisit:

- **RBAC**: reads use `CurrentUser`, mutations use `RequireAdmin`. Change the dependency per
  route if the resource is self-service or public-readable.
- **Validation**: the service only maps `IntegrityError` to `ConflictException`. Domain
  invariants, normalization helpers and `ValidationException` cases are yours.
- **Endpoints**: the slice ships list, create, get and update. Deletion is absent on purpose —
  decide soft-disable (`disabled_at`, 200 + envelope) or hard delete (204, added to
  `NO_CONTENT_ROUTES` and `ENVELOPE_EXEMPT_ROUTES` in `test_route_contracts.py`).
- **Uniqueness and indexes**: the model has only a UUID key and timestamps; add the
  `UniqueConstraint`/`Index` the domain needs before the first migration.
- **Frontend detail/create screens**: only the list route is generated. `use-create-<entity>.ts`
  and the zod schemas are there for the form; the form container and `/<feature>/new` route are
  not.
- **MSW**: the container test registers its own handler. Move shared handlers into
  `src/testing/msw/handlers.ts` when a second feature needs them.

## Harness notes

- **Claude Code** — invoked as `/scaffold-crud`. Run the generators with the Bash tool; present
  the `--plan` JSON in the message that asks for approval, not as a file the user must open.
- **Codex** — invoked as `$scaffold-crud`. Same commands; `codex --cd backend` will not see the
  repo-root paths, so run from the repository root.
