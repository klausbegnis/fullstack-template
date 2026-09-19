---
name: orchestrate
description: Drive a batch of independent work items through the existing /task pipeline concurrently, with a bounded worker pool, per-task worktree/branch/compose isolation, pre-dispatch overlap detection (migration-touching tasks always serialized to a single alembic head), disk-persisted resumable run state, orphan reclamation, and a final PR/gate summary table. Invoked as `/orchestrate <items>` (newline- or `-`-delimited) or `/orchestrate --backlog=<path> [--concurrency=N] [--gate=manual|auto] [--run=<id>] [--strict-overlap]`. Use for a batch/backlog of independent tasks to ship in parallel, "run these N tasks concurrently", "process the backlog", "fan /task out over this list", or when an external loop (cron, Hermes, a queue consumer) re-invokes to advance a run. Do NOT use for one piece of work — call /task directly — and do not use it to review existing code, merge PRs, or answer a question.
---

# orchestrate — bounded concurrent /task fan-out

You are the **pool manager**, not a second pipeline. You never plan, implement, or review
code yourself, and you never edit a worktree. Every unit of work is a full, unmodified run
of `.claude/skills/task/SKILL.md`, dispatched as an isolated subagent. You hold only a small
status record per task — never that task's diff, plan, or transcript.

## Invocation

`/orchestrate <items...> [--concurrency=N] [--gate=manual|auto] [--run=<id>] [--strict-overlap]`

| Argument | Meaning | Default |
|---|---|---|
| `<items>` | The backlog. See **Input forms** below. | required |
| `--backlog=<path>` | Read items from a file instead of inline args. | — |
| `--concurrency=N` | Max tasks in flight at once. | **3** |
| `--gate=manual\|auto` | Forwarded verbatim to every `/task` dispatch unless a line overrides it. | `auto` |
| `--run=<id>` | Pin the run id for resume. Omit to derive one deterministically. | derived |
| `--strict-overlap` | Refuse file-overlapping tasks instead of serializing them. Never applies to migrations — those are always serialized, no override. | off |

**Input forms** (pick one):
1. Inline arguments, one task per line (a multi-line string or heredoc-style argument).
2. A `-`/`*` bulleted list, inline or in a file — the bullet marker is stripped.
3. `--backlog=<path>` — a plain-text or markdown-checklist file, one task per line. Blank
   lines and lines starting with `#` are ignored. A `- [x]` checked line is skipped (treated
   as already handled outside this run); `- [ ]` and unmarked lines are work items.

Each line may end with its own `--gate=` override, which wins over the run default for that
task only.

## Concurrency default: 3, and why

Each in-flight task provisions a **full docker compose stack** via `task_env.py up`
(db + api + frontend). Port allocation (`PORT_SCAN_LIMIT=400` per service) is not the
binding constraint — host CPU/memory for N concurrent compose stacks, and the number of
opus-model subagents you can dispatch and later reconcile without silently losing track of
one, are. Three is the largest pool that keeps every in-flight PR reviewable by a human at
`--gate=manual` without a backlog of unread gate reports, and matches `/task`'s own
conservatism about round counts. Raise `--concurrency` on a beefier box; lower it to 1 to
force strict sequential processing without changing anything else about this skill.

## The graph — this is the order authority

```mermaid
flowchart TD
  O0[O0 pre-flight] --> O1[O1 intake + run resolve]
  O1 --> O2[O2 overlap + migration scan]
  O2 --> O3[O3 lane assignment]
  O3 --> O4[O4 orphan reclamation]
  O4 --> O5[O5 dispatch wave]
  O5 --> O6[O6 collect + persist]
  O6 -->|a lane is free and has a pending task| O5
  O6 -->|no lane can advance right now| O7[O7 final report]
```

**One todo item per node.** Create the whole list at O0.

```
O0 pre-flight              O4 orphan reclamation
O1 intake + run resolve    O5 dispatch wave
O2 overlap scan            O6 collect + persist
O3 lane assignment         O7 final report
```

O5↔O6 is the pool's drain loop, not a failure loop-back — it repeats every time a slot frees
and the backlog still has eligible work, within the same invocation, until nothing more can
be started right now.

## Invariants

- **You never touch a worktree, branch, or compose project directly**, except read-only
  inspection (`git worktree list`, `docker compose ls`, `task_env.py status`) for orphan
  reclamation. `/task` owns all of that; duplicating it here is how two owners collide.
- **State lives on disk**, at `${TMPDIR:-/tmp}/orchestrate-runs/<run-id>/state.json`, outside
  every worktree and outside `/task`'s own `${TMPDIR:-/tmp}/task-qa/` state root. If your
  context is compacted or this invocation is a resume, re-read it before acting.
- **Each `/task` run is dispatched as its own subagent** (`general-purpose`, `model: opus` —
  it performs the entire `/task` orchestrator role, the same reason `/task` pins opus for its
  own implementer and QA). Give it nothing but the template in **O5**. Take back nothing but
  the one-block report in **O6**. Never paste a task's plan, diff, or check output into your
  own context or into another task's dispatch.
- **A run-scoped lock** at `$STATE_DIR/lock` (pid + timestamp) prevents two orchestrate
  invocations from double-dispatching the same run. Refuse to start if a live lock is younger
  than 2 hours; otherwise treat it as abandoned and proceed.
- **Teardown is `/task`'s job, always**, per its own T11. Your orphan reclamation (O4) exists
  only to catch what a *killed* orchestrate or `/task` subagent — one that never reached
  T11 — left behind. It is a safety net, not the primary teardown path.
- **Never dispatch a task whose predicted worktree/branch already has an unresolved state**
  you have not read. Predicted paths come from `task_env.py slug`, which is a pure function
  of the description — compute it once, pin it in `state.json`, and reuse it forever for that
  task, including across resumes on a different calendar day.

## O0 — pre-flight
**Purpose.** Fail before touching disk if the toolchain is missing.
**Do.** `git --version; gh auth status; docker compose version; python3 --version` plus
`git -C "$(git rev-parse --show-toplevel)" worktree list`.
**Exit.** All present, `gh` authenticated.
**On failure.** Hard stop, list what is missing. Never auto-install.
**Produces.** The todo list.

## O1 — intake + run resolve
**Purpose.** Fix the backlog and the run identity before any dispatch exists.
**Do.**
```
ROOT=$(git rev-parse --show-toplevel)
RUN=${RUN_OVERRIDE:-"$(date -u +%F)-$(printf '%s' "$RAW_INPUT" | sort | shasum -a 1 | cut -c1-8)"}
STATE_DIR="${TMPDIR:-/tmp}/orchestrate-runs/$RUN"
mkdir -p "$STATE_DIR"
printf '%s\n' "$RAW_INPUT" > "$STATE_DIR/backlog.txt"
```
`$RAW_INPUT` is the parsed, one-task-per-line backlog per **Input forms** (bullets and
comments stripped). If `$STATE_DIR/state.json` already exists, this is a **resume**: load it
instead of building a fresh one, and skip straight to O4 with the existing task list — do not
re-run O2/O3 on tasks that already have a lane and a status. Only merge in genuinely new lines
(present in the fresh backlog, absent from the loaded state) through O2/O3.
Write the lock: `printf '%s %s\n' "$$" "$(date -u +%FT%TZ)" > "$STATE_DIR/lock"`.
For a fresh run, seed `state.json`:
```json
{
  "run_id": "<RUN>",
  "gate_mode": "auto",
  "concurrency": 3,
  "strict_overlap": false,
  "tasks": [
    {
      "id": "t1",
      "description": "<verbatim line>",
      "slug": "<task_env.py slug output>",
      "date_pin": null,
      "migration": false,
      "lane": null,
      "status": "pending",
      "worktree": null,
      "branch": null,
      "pr_number": null,
      "pr_url": null,
      "gate1": null,
      "gate2": null,
      "failure_reason": null,
      "evidence_path": null,
      "started_at": null,
      "finished_at": null
    }
  ]
}
```
Compute `slug` for every task now via `python3 .claude/skills/task/task_env.py slug "<description>"`
— never hand-derive it; it must agree with what `/task` itself will compute at its own T1.
**Exit.** `state.json` exists, every task has an `id` and a `slug`, the lock is held.
**On failure.** A live lock younger than 2 hours → stop, report who holds it, do not proceed.

## O2 — overlap + migration scan
**Purpose.** Flag tasks that will conflict at merge before either one is dispatched. This is
static and cheap — no subagent, no LLM call.
**Do.** For every task new to this run:
1. **Migration tag.** Match the description case-insensitively against
   `\b(migration|alembic|schema|column|drop table|new table|rename table|add.*model|model field)\b`.
   Any hit → `migration: true`.
2. **Predicted file hits.** Extract tokens ≥4 chars, minus stopwords, from the description.
   Keep only tokens that also occur as a file or directory basename under `backend/app` or
   `frontend/src`:
   ```
   git -C "$ROOT" ls-files backend/app frontend/src | xargs -n1 basename | sort -u
   ```
   Grep the repo for the surviving tokens to get each task's predicted hit set:
   ```
   git -C "$ROOT" grep -liE '(tok1|tok2|...)' -- backend/app frontend/src
   ```
3. **Pairwise overlap.** Two non-migration tasks overlap when their predicted hit sets
   intersect. Record the pair.
This is a heuristic, not a guarantee — it exists to catch the common case (two tasks naming
the same router, model, or component) cheaply, not to prove independence formally.
**Exit.** Every task has `migration` set, and every overlapping pair is recorded.
**Produces.** The overlap-pair list and the migration-tagged set, consumed by O3.

## O3 — lane assignment
**Purpose.** Turn overlap findings into a dispatch order that cannot produce two colliding
merges. A lane is a strict FIFO queue; different lanes run concurrently, up to `--concurrency`.
**Do.**
- **Migrations lane, mandatory, no override.** All `migration: true` tasks go into one lane,
  `lane: "migrations"`, in backlog order. `alembic` has one linear head; two worktrees
  branched from the same `origin/main` each adding a revision will produce two heads the
  moment both merge, regardless of whether their code changes overlap. Serializing *dispatch*
  is not enough — the next migration task must not even be dispatched until the previous
  migration task's PR has actually **merged** into `origin/main`, not merely reached
  ready-for-review. Gate its admission on:
  ```
  gh pr view <prev-pr-number> --json state --jq .state
  ```
  `MERGED` → admit the next migration task. `OPEN` → leave it `status: "blocked-on-merge"`
  and do not dispatch it this invocation; a later invocation re-checks. `CLOSED` (abandoned,
  unmerged) → stop and report to the human; do not auto-advance the lane.
- **File-overlap lanes.** For every recorded overlapping pair, put both tasks in one shared
  lane (union overlapping pairs transitively into groups), FIFO by backlog order. Admission
  into the next slot only requires the previous lane member to reach any terminal status
  (`passed`, `hard-stop`, `gate1-fail`, `gate2-fail`) — unlike migrations, nothing here
  requires a merge, because two open, un-merged branches touching the same file do not
  corrupt each other; the risk is a messy merge later, which serialized *dispatch order*
  already reduces, and a human resolves the rest at merge time.
- With `--strict-overlap`: skip the shared-lane construction for file overlaps (never for
  migrations) and instead mark every task in an overlapping pair `status: "blocked-overlap"`,
  `failure_reason: "overlaps with <other task id>; rerun with default serialization or split the work"`.
  Do not dispatch them.
- Every task touched by neither rule gets its own singleton lane — it runs the moment a pool
  slot is free.
**Exit.** Every non-blocked task has a `lane`. Persist `state.json`.

## O4 — orphan reclamation
**Purpose.** Reclaim what a killed `/task` or `orchestrate` process left behind, from *this*
run or any other. Runs on every invocation, before dispatching, because it is cheap and the
alternative is silent port/worktree exhaustion.
**Do.** List candidates:
```
find "${TMPDIR:-/tmp}/task-qa" -maxdepth 1 -mindepth 1 -type d -mmin +240
docker compose ls --format '{{.Name}}' | grep '^task-'
git -C "$ROOT" worktree list --porcelain | awk '/^worktree /{print $2}' | grep '/.task-worktrees/'
```
A candidate slug is an **orphan** only if it is both older than 4 hours (the `-mmin +240`
filter, or the worktree's directory mtime) **and** absent from every non-terminal task in
every `${TMPDIR:-/tmp}/orchestrate-runs/*/state.json` — i.e. no live run, including this one,
still claims it. Never reclaim a slug that any run's state file lists as `pending`,
`dispatched`, or `blocked-on-merge`.
Before removing a worktree, check it is safe:
```
git -C "<worktree>" status --short
git -C "<worktree>" log @{u}.. --oneline
```
Non-empty either way → **stop, report, do not remove.** Unpushed or uncommitted work is never
destroyed silently. Otherwise:
```
python3 .claude/skills/task/task_env.py down --task <slug>
git -C "$ROOT" worktree remove "<worktree>" --force
git -C "$ROOT" worktree prune
```
`task_env.py down` refuses any project not prefixed `task-` and requires an explicit
`--task`, so this can never reach the developer's main stack.
**Exit.** No orphan candidate remains that met both conditions.
**On failure.** A candidate with unsafe state → leave it, name it in the final report.

## O5 — dispatch wave
**Purpose.** Fill every free pool slot with the next eligible task, then dispatch all of them
in one message so they run concurrently (multiple `Agent` calls in a single message do; the
wave waits for the whole batch to return before you can see any of it, which is why this is a
wave, not a stream — refill happens in the O5↔O6 loop instead).
**Do.** A slot is free when fewer than `--concurrency` lanes currently have a task
`status: "dispatched"`. For each free slot, in lane order: take the head of the first lane
with a `pending` task and no task currently `dispatched`. For a task never dispatched before,
set `date_pin = date -u +%F` now and freeze it in `state.json` — every later redispatch of
this same task reuses this value, so paths stay stable across a resume that crosses midnight.
Dispatch each chosen task as one `Agent` call, `general-purpose`, `model: "opus"`, in a single
message covering the whole wave. Prompt, verbatim except the placeholders:
```
Follow .claude/skills/task/SKILL.md exactly, end to end, for this work item. Do not ask
about scope; the description below is the whole task.

Task: <verbatim description>
Gate mode: --gate=<auto|manual>
Pinned DATE for T1: <date_pin> — use this exact value, do not compute today's date.

If <ROOT>/../.task-worktrees/<date_pin>-<slug> already exists and contains
.tasks/<date_pin>-<slug>.md, this is a resume: cd into that worktree, read the task file's
progress log, and continue from the last logged node instead of starting at T0.

When you finish — success, a gate failure, or a hard stop — return exactly one block and
nothing else:
STATUS: passed | gate1-fail | gate2-fail | hard-stop
PR: <number and URL, or none>
WORKTREE: <absolute path if kept, or removed>
REASON: <one line, only if not passed>
```
Mark each dispatched task `status: "dispatched"`, `started_at: now`, persist `state.json`
immediately — a crash between dispatch and collection must find these as resumable, not lost.
**Exit.** Every free slot this pass either got a task or had none eligible.
**Produces.** The wave's Agent results, arriving together in O6.

## O6 — collect + persist
**Purpose.** Turn each subagent's one report block into a state update, without absorbing
anything else it may have said.
**Do.** For each returned result, parse the `STATUS:`/`PR:`/`WORKTREE:`/`REASON:` block only.
Update that task's row: `status`, `pr_number`, `pr_url`, `worktree`, `failure_reason`,
`finished_at`. Derive `gate1`/`gate2` from `status` (`gate1-fail` → G1 failed, G2 never run;
`gate2-fail` → G1 passed, G2 failed; `hard-stop` → record which gate was in progress from the
reason line; `passed` → both green). Release the task's lane. Persist `state.json`.
**Exit.** Every wave member has a terminal or `blocked-on-merge` status recorded.
**Loop.** If any lane now has a free head and a `pending` (or a `blocked-on-merge` that just
became admittable — re-check `gh pr view` for the migrations lane) task, return to **O5**.
Otherwise fall through to **O7**.

## O7 — final report
**Purpose.** One table, everything a human or the external loop needs, nothing they must dig
for.
**Do.** Release the lock (`rm "$STATE_DIR/lock"`). Print a table: task, status, PR link, G1,
G2, and — for anything not `passed` — the failure reason and where the evidence lives (task
file path if the worktree was kept, PR URL, or the QA handoff dir at
`${TMPDIR:-/tmp}/task-qa/<slug>/`). Then one line: how many tasks remain `pending` or
`blocked-on-merge`, and that re-invoking `/orchestrate` with the same `--run=<id>` (or letting
the external loop do so) resumes exactly them.
**Exit.** Report printed. State file is the durable record; do not delete it.

## Resumability

`state.json` is the entire memory of a run. Resume procedure, always safe to run cold:
1. `RUN=<id>`; if unknown, `ls "${TMPDIR:-/tmp}/orchestrate-runs/"` and pick by recency.
2. Load `state.json`. Any task `status: "dispatched"` with no terminal result means the prior
   orchestrate process died mid-wave, not that the task itself failed. Re-dispatch it exactly
   as in O5, using its **already-pinned** `slug` and `date_pin` — the resume clause in the
   dispatch prompt handles a worktree that already exists.
3. Skip every `passed`/`gate1-fail`/`gate2-fail`/`hard-stop` task entirely. This is what makes
   a re-invocation idempotent: nothing already terminal is ever redispatched.
4. Re-run O4 (orphan reclamation is always safe and cheap) before O5.
5. Continue the O5↔O6 loop from wherever the lanes stand.

A single invocation is one call to this procedure: drain everything currently dispatchable,
report, exit. The external loop's only job is to call `/orchestrate --run=<id>` again later —
it owns pacing (how often, whether to add new backlog lines to the same run via `--backlog=`),
never the pool logic, lane logic, or gate logic, all of which live here and in `/task`.

## Failure isolation

One task's `gate1-fail`/`gate2-fail`/`hard-stop` never aborts the run. Concretely:
- **Worktree.** `/task` keeps it on any failure path (its own T11 invariant) — you do not
  remove it. It is where the human resumes.
- **Compose project.** `/task`'s T11 always runs `task_env.py down --task <slug>`, win or
  lose — teardown is unconditional, only the worktree survives.
- **Branch/PR.** Whatever existed at the point of failure stays exactly as `/task` left it: no
  PR if it failed before T9, a draft PR if it failed at G2 (QA never flips it ready), pushed
  commits regardless. You never merge, close, or edit a PR.
- **Lane.** The slot is released in O6 like any terminal status; later tasks in the same lane
  proceed normally — a failed task was never merged, so it cannot poison a peer's merge base.
- **Report.** Every failure appears in O7 with its reason and evidence path. Nothing failed is
  ever silently dropped from the table.

## Files in this skill

| File | Role |
|---|---|
| `SKILL.md` | This file. The pool graph, the nodes, the lane and resume rules. |

No companion script: slug derivation and environment teardown are `/task`'s
`task_env.py`, reused as-is (`slug`, `status`, `down`) so the two skills can never disagree
about a task's identity.
