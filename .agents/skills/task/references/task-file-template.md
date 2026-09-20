# Task file template

Write this to `<worktree>/.tasks/<YYYY-MM-DD>-<slug>.md` at **T3**. It is the pipeline's
durable state: every node reads it and every node appends to it.

- It **is** committed at T9 and **is** the draft PR's body.
- It **is deleted** by `git rm` in T10's final commit. It must never reach `main`.
- The permanent record is the PR body built from it at T10, not this file.
- Never gitignore `.tasks/`.

Sections below are mandatory and appear in this order. Do not reorder them; the PR body is
assembled by reading them in sequence.

---

```markdown
# <short imperative title>

## Task
Description: <the invocation text, verbatim — never paraphrased>
Gate mode: auto | manual
Branch: task/<YYYY-MM-DD>-<slug> | <type>/<issue-number>-<slug>
Worktree: <absolute path>
Base: origin/main @ <sha>
Slug: <slug>
Source: #<issue-number> <issue-url>        <!-- only when T1's source is an issue -->
PRD: <docs/prds/NNNN-slug.md>              <!-- only when Related documents named one -->

## Exploration            <!-- T4 -->
Where this lives today:
- <path:line> — <what it does>
Already exists (do not duplicate):
- <path:line> — <what>
Rejected approach:
- <the obvious implementation> — rejected because <reason, with evidence>
Repo rules in play:
- <layering / import boundaries / envelope / migration / no-comments rule that applies>

## Plan                   <!-- T5 -->
Scope: backend | frontend | both
Contract sync required: yes | no   <!-- yes when routers/, schemas/ or main.py change -->

| File | Change | Why |
|---|---|---|
| backend/app/... | ... | ... |

Test strategy:
- <for a bug: the failing test that comes first, by path and name>
- <new tests, by path>
Migration:
- <new revision and what it does, or "none">

Acceptance criteria (observable behaviour, not tasks):
1. <e.g. `GET /users?page=2&page_size=10` returns PaginatedResponse with page=2>
2. <e.g. a member calling `DELETE /users/<other-id>` gets 403 with the error envelope>

## Implementation log     <!-- T6, appended by the implementer subagent -->
- <path:line> — <what changed>

## G1 evidence            <!-- T7 + T8 -->
### Checks
| Command | Result |
|---|---|
| backend: uv run ruff format --check . | PASS |
| backend: uv run ruff check . | PASS |
| backend: uv run mypy app | PASS |
| backend: uv run alembic upgrade head | PASS |
| backend: uv run alembic check | PASS — no new upgrade operations detected |
| backend: uv run pytest | PASS — 79 passed |
| frontend: npm run lint | PASS |
| frontend: npm run typecheck | PASS |
| frontend: npm run format | PASS |
| frontend: npm run test | PASS — <n> files, <n> tests |
| frontend: npm run build | PASS |

A command that was not run is written `UNVERIFIED — <reason>`, never folded into PASS.

### Review
| Reviewer | Verdict | Blockers | Resolution |
|---|---|---|---|
| backend-reviewer | PASS / FAIL (n) | <file:line — issue> | fixed in <sha> / refuted by <measurement> |
| frontend-reviewer | ... | ... | ... |
| uncle-bob | ... | ... | ... |

## Handoff                <!-- H — pointer only -->
Handoff file: ${TMPDIR:-/tmp}/task-qa/<slug>/handoff.md
(The handoff itself lives outside the worktree so it is never committed and survives the
deletion of this file.)

## G2 evidence            <!-- filled from the QA result block -->
Verdict: PASS | FAIL
Iterations: <n>

| Case | Expected | Actual | Result | Evidence |
|---|---|---|---|---|
| C1 | ... | ... | PASS | <log/response pointer> |

Changed during QA: <file:line — what> | none
QA report comment: <url>

## Progress log           <!-- appended at every node, never rewritten -->
- [T0] 2026-09-19T14:01Z — pre-flight green (git, gh, docker, uv, node)
- [T1] 2026-09-19T14:01Z — slug=<slug>, gate=auto
- [T2] 2026-09-19T14:02Z — worktree at <path>, branch task/<...>
- ...
```

---

## Progress log rules

- One line per node entry, `- [<node>] <ISO-8601 UTC> — <what happened>`.
- Append on **entering a loop-back** too: `- [G1] ... — FAIL, 1 blocker, loop back to T6`.
- On resume after a crash or a compaction: read this log, take the last node, re-verify its
  exit condition, and continue from there. Never restart from T0 on a worktree that already
  exists.
