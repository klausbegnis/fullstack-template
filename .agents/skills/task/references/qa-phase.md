# QA phase — Q0 to Q9

You are the **QA subagent** of the `/task` pipeline. You start with a clean context and
that is deliberate: you must judge the change from its acceptance criteria and the running
system, not from the orchestrator's beliefs about it.

**Your only source of truth is the handoff file** whose absolute path you were given. Read
it first. You do **not** need — and must not read — the pipeline's `SKILL.md`. Read the
plan from the task file only through the path the handoff gives you.

## The graph

```
Q0 scope  ->  Q1 up  ->  Q2 smoke  ->  Q3 cases  ->  Q4 execute  ->  Q5 evidence  ->  Q6 verdict
                            |                                                          |    |
                            +--------------------> Q7 diagnose + fix <-----------------+    |
                                                        |  (max 5 iterations, back to Q4)   |
                                            Q9 fail-stop + teardown            Q8 green report + teardown
```

Create one todo per node before you start. A skipped node must be visible as a missing
checkbox, never a silent shortcut.

## Invariants

- **Never mark QA complete with a red case.** A partially-green run is `FAIL`.
- **Every path ends in teardown**, including a crash, a timeout, and the fail-stop.
- **Evidence or it did not happen.** Each case needs all three evidence types from Q5.
- **Cases come from the acceptance criteria, never from the diff.** Reading the diff to
  build cases tests what the code does, which is circular.
- **Fix the criterion before you run.** Never adjust an expectation after seeing the actual.
- **Update the `State` section of the handoff file after every node.** If your context is
  compacted, that file is how you resume.
- **Foreground only.** Never leave a suite or a container command running when you return.
- **Secrets.** `task_env.py` generates this stack's `AUTH_JWT_SECRET`. Use it via
  `task_env.py env --export`; never print it, never read `.env` files, never paste a token
  body into your report. Use short, obviously-fake test passwords.
- **Max 5 iterations** of Q4→Q7 on the same case. On the sixth, go to Q9.

Throughout, `$SLUG`, `$WT` (worktree) and `$PR` come from the handoff file.

---

## Q0 — classify scope
**Purpose.** Decide which services must run.
**Do.** Read `Scope` from the handoff and map it:

| Handoff scope | `--services` | Why |
|---|---|---|
| `backend` | `db,api` | No UI to exercise; save the frontend build |
| `frontend` | `db,api,frontend` | The UI is useless without the API it proxies to |
| `both` | `db,api,frontend` | Full stack |

**Exit.** A services list, written to `State`.

## Q1 — bring the environment up
**Purpose.** Run *this branch's* code, isolated from every other task and from the
developer's own stack.
**Do.**
```
python3 "$(git rev-parse --show-toplevel)"/.agents/skills/task/scripts/task_env.py up --task "$SLUG" --worktree "$WT" \
  --services <from Q0> --build
eval "$(python3 "$(git rev-parse --show-toplevel)"/.agents/skills/task/scripts/task_env.py env --task "$SLUG" --export)"
```
`--build` is mandatory here and after every Q7 fix: the images are built from the worktree
and are stale otherwise. `up` waits for healthchecks; the `api` entrypoint runs
`alembic upgrade head`, so the database arrives migrated.
**Exit.** `up` returned 0. Record `$API_BASE_URL`, `$FRONTEND_BASE_URL` and the ports in
`State`.
**On failure.** `task_env.py logs --task "$SLUG" -n 200`, diagnose, then Q7 — never test
against a half-started stack.

## Q2 — smoke
**Purpose.** Separate "the change is wrong" from "nothing is running".
**Do.**
```
curl -fsS "$API_BASE_URL/health"
curl -fsS -o /dev/null -w '%{http_code}\n' "$FRONTEND_BASE_URL"
python3 "$(git rev-parse --show-toplevel)"/.agents/skills/task/scripts/task_env.py logs --task "$SLUG" -n 100
```
Run the frontend line only when the frontend is in scope. Expect `/health` to return the
`SuccessResponse` envelope, the frontend to return 200, and the logs to contain no
traceback and no repeating restart.
**Exit.** All three clean. **On failure.** Q7.

## Q3 — derive the cases
**Purpose.** Fix what "working" means, in writing, before running anything.
**Do.** Take each acceptance criterion from the handoff and turn it into at least one case
with a concrete input and a verifiable expected output. Write the table into `State`
**before** Q4. Every set of cases must include:

- one **happy path** per criterion;
- one **negative** case (bad input → the repo's error envelope
  `{"error": {"code", "message", "details"}}` with the right status);
- one **anti-false-positive** case: an input that must *not* trigger the new behaviour.
  Without it you cannot tell a working feature from an endpoint that always says yes.
- for anything touching auth or roles: one case as a **non-owner / non-admin** user that
  must be rejected.

Useful fixtures for this repo:
```
docker compose -p "task-$SLUG" exec api \
  python -m app.commands.bootstrap_admin qa-admin@example.test --password 'qa-not-a-real-pw' --yes
docker compose -p "task-$SLUG" exec api \
  python -m app.commands.bootstrap_user qa-user@example.test --password 'qa-not-a-real-pw' --member
```
`bootstrap_admin` requires `--yes`; `bootstrap_user` creates an admin unless you pass
`--member`, so pass `--member` whenever you need a non-privileged actor.
Routes are unprefixed on the API (`/health`, `/auth/login`, `/auth/me`, `/users/...`) and
prefixed on the frontend proxy (`/api/...`, rewritten by `next.config.ts`).
**Exit.** A case table with `id | input | expected` fixed and recorded.

## Q4 — execute
**Purpose.** Run the cases against the running stack.
**Do.** One command per case, in the foreground. Authenticated flows use a cookie jar:
```
curl -fsS -c "$JAR" -X POST "$API_BASE_URL/auth/login" \
  -H 'content-type: application/json' \
  -d '{"email":"qa-user@example.test","password":"qa-not-a-real-pw"}'
curl -fsS -b "$JAR" "$API_BASE_URL/auth/me"
```
**Trap, verified:** the refresh cookie is scoped to path `/api/auth`, so
`$API_BASE_URL/auth/refresh` will not receive it. Exercise refresh and logout **through the
frontend proxy** — `$FRONTEND_BASE_URL/api/auth/refresh` — and send the CSRF value from the
readable `app_csrf` cookie in the `x-csrf-token` header. A refresh test that "fails" against
the API port directly is your mistake, not a defect.

If the plan added or changed tests, also run the affected suite inside the worktree
(`cd "$WT/backend" && uv run pytest tests/...` or `cd "$WT/frontend" && npm run test`) —
but a green suite is never a substitute for exercising the running stack.
**Exit.** Every case has an actual result.

## Q5 — collect evidence
**Purpose.** Make the verdict checkable by someone who was not here.
**Do.** Per case, collect exactly three things:

| Evidence | How | Rule |
|---|---|---|
| Response | status code + the judged fields of the body | Big body → write it to the state dir and quote only the fields the criterion names |
| Logs | `task_env.py logs --task "$SLUG" --service api -n 50` **since the request** | Never dump the full log |
| State proof | a DB read or a follow-up request proving the effect persisted | A 200 alone does not prove a write happened |

Budget: about two commands per case. Four or five means you are re-reading instead of
measuring.
**Exit.** The case table in `State` carries expected, actual and evidence per row.

## Q6 — verdict
**Purpose.** Compare against the criterion fixed in Q3, and nothing else.
**Do.** All cases green → **Q8**. Any case red → **Q7**. A case you could not execute is
red, not skipped.
**Never** relax a criterion, reinterpret "expected", or declare a case out of scope here.
If a criterion turns out to be genuinely ambiguous, that is a Q9 fail-stop with the exact
question — not a judgement call you make alone.

## Q7 — diagnose and fix
**Purpose.** Close the loop inside QA when the fix is small and certain.
**Do.**
1. Locate the cause from the evidence plus targeted reads (`sed -n 'A,Bp'`, `grep -n`).
   Never `cat` whole files, never chain `cat`s.
2. Fix it **inside `$WT`** only. Add no inline comments.
3. If the fix touched backend routers/schemas: re-export the contract —
   `cd "$WT/backend" && uv run python -m app.commands.export_openapi`, then
   `cd "$WT/frontend" && npm run generate:api`.
4. Re-run the affected repo checks for the side you touched (`uv run ruff check .`,
   `uv run mypy app`, `uv run pytest` / `npm run lint`, `npm run typecheck`, `npm run test`).
   Red checks are never left for the orchestrator.
5. Commit on the task branch and push:
   `git -C "$WT" add -A && git -C "$WT" commit -m "fix: <what>" && git -C "$WT" push`.
6. `task_env.py up --task "$SLUG" --worktree "$WT" --services <Q0> --build` to rebuild.
7. `iteration += 1`; return to **Q4** and re-run the failed case **and every previously
   green case** — a fix that breaks a green case is a regression, not progress.

**Escalate to Q9** when: `iteration == 5` without the case going green; or the fix would
change the plan's scope, a migration's meaning, or an acceptance criterion; or the cause is
outside the diff (pre-existing defect, infrastructure). Do not silently widen the task.

## Q8 — green report and teardown
**Do., in this order:**
1. Confirm the branch is pushed and the working tree in `$WT` is clean.
2. Comment the QA report on the PR:
   ```
   gh pr comment "$PR" --body-file <state-dir>/qa-report.md
   ```
   The report is a markdown table `case | expected | actual | evidence`, plus the iteration
   count and a one-line list of anything you changed in Q7.
3. **Teardown:** `python3 "$(git rev-parse --show-toplevel)"/.agents/skills/task/scripts/task_env.py down --task "$SLUG"`.
4. Return the result block, and nothing else.

Do not flip the PR out of draft, do not edit the PR body, do not delete the task file, do
not remove the worktree — the orchestrator owns all of that.

## Q9 — fail-stop
**Do.** Same order as Q8, with the honest content:
1. PR comment: the green cases, the stuck case with expected vs actual, the diagnosis, the
   hypotheses you discarded and why, and the evidence for the stuck case too.
2. **Teardown:** `task_env.py down --task "$SLUG"`.
3. Return the result block with `verdict: FAIL` and the exact question a human must answer.

Never report a red case as "mostly working". Never leave the stack up "so someone can look".

---

## Result block — the only thing you return

Return this and nothing else. No preamble, no narration, no re-statement of the diff.

```
verdict: PASS | FAIL
slug: <slug>
scope: <backend|frontend|both>  services: <db,api,frontend>
ports: db=<n> api=<n> frontend=<n>
iterations: <n>
cases:
  - <id> | <expected> | <actual> | PASS|FAIL | <evidence pointer>
changed_in_qa:
  - <file:line — what> | none
commits: <sha> <sha> | none
pr_comment: <url>
teardown: done
blocked:            # only when verdict: FAIL
  case: <id>
  diagnosis: <one or two lines>
  discarded: <hypotheses already ruled out>
  question: <the exact decision the human must make>
```
