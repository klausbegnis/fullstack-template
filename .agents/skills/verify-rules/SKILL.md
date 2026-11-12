---
name: verify-rules
description: Self-test the enforcement layer by planting the deliberate rule violations from the plan's Verification set into a throwaway worktree, running the gates, and reporting which check caught each probe and which caught nothing. Run it after editing `frontend/eslint.config.mjs`, an architecture test under `backend/tests/unit/architecture/`, `src/testing/architecture.node.test.ts`, or a rule file's `Enforced by:` line. Never run it against a working tree that holds real changes.
disable-model-invocation: true
---

# verify-rules

A rule whose `Enforced by:` line names a check that no longer fires is prose pretending to be a
gate. This skill proves, per rule, that the gate still goes red.

## Safety

Every step happens in a **throwaway worktree on a throwaway branch**. Never plant a probe in a
tree that holds work: a failed cleanup would leave a deliberate violation in a commit.

## 1. Isolate

```bash
ROOT=$(git rev-parse --show-toplevel)
STAMP=$(date +%s)
git -C "$ROOT" worktree add -b verify-rules/$STAMP "$ROOT/../verify-rules-$STAMP" HEAD
cd "$ROOT/../verify-rules-$STAMP"
ln -s "$ROOT/frontend/node_modules" frontend/node_modules
(cd backend && uv sync)
```

Give the worktree its own `backend/.venv` with `uv sync` rather than symlinking the main tree's:
`uv run` rewrites the editable install path, and a symlinked venv would repoint the main tree's
imports mid-run.

## 2. Baseline

Run both gates **before** planting anything and record that they are green. A probe that "fails"
a check which was already red proves nothing.

```bash
(cd backend && TESTING=true uv run pytest tests/unit -q)
(cd frontend && npm run lint && npm run test:fast)
```

## 3. Plant

```bash
python3 "$ROOT/.agents/skills/verify-rules/scripts/plant_violations.py" --list
python3 "$ROOT/.agents/skills/verify-rules/scripts/plant_violations.py" --plant
```

The probe set is one file per mechanical rule: a `model/` module importing `@tanstack/react-query`;
a `features/*/components/` view with `'use client'`; a feature hook calling
`dialog.showModal()` (`feature-show-modal`, caught by `no-restricted-properties`); a barrel
`index.ts`; an async `page.tsx` with no `loading.tsx`; a router importing `app.models`; a repository calling `.commit()`; a route with
no auth dependency (the planter also registers it in `main.py`, since route contracts read the
live app); and a service with no paired test module. `--probe <name>` plants a subset; each entry
carries the `expected_failure` — the check that must catch it.

## 4. Run the gates and attribute each failure

```bash
(cd backend && TESTING=true uv run pytest tests/unit -q) ; echo "backend exit=$?"
(cd frontend && npm run lint) ; echo "lint exit=$?"
(cd frontend && npm run test:fast) ; echo "arch tests exit=$?"
```

Read the failures and map each back to a probe. Report one row per probe:

| Probe | Expected check | Caught by | Verdict |
|---|---|---|---|
| `model-imports-tanstack` | `npm run lint` | … | caught / **UNCAUGHT** |

`UNCAUGHT` is the finding worth having: it means that rule's `Enforced by:` line is wrong and the
rule is review-only until the check is fixed. Say which rule file and which line.

A probe caught by a *different* check than the one named is also a finding — the `Enforced by:`
line needs correcting.

## 5. Clean up

```bash
python3 "$ROOT/.agents/skills/verify-rules/scripts/plant_violations.py" --clean
git status --short          # must show nothing but the worktree's own untracked deps
cd "$ROOT"
git worktree remove --force "$ROOT/../verify-rules-$STAMP"
git branch -D verify-rules/$STAMP
```

`--clean` removes a probe only when its content still matches what was planted, so a file you
edited is left alone and shows up in `git status` instead of disappearing silently. Confirm the
worktree is gone before reporting.

## Harness notes

- **Claude Code** — `disable-model-invocation: true`: this skill only runs when a human types
  `/verify-rules`. It must never be triggered by a model reading about enforcement.
- **Codex** — invoked as `$verify-rules`. Codex reads only `name` and `description` from the
  frontmatter, so the "never run this unasked" constraint lives in this section and in the
  description; state it back before starting.
