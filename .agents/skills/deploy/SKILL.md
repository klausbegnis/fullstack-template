---
name: deploy
description: Ship what is on `main` to the production VPS, by hand, through `scripts/deploy-vps.sh`. Invoked as `deploy [--ref <main commit>]`. Checks that the commit is on `origin/main` and that CI passed on it, shows the plan, deploys after the human confirms, verifies the site from outside and reports. Use only when a human asks to deploy, redeploy or roll back production. Never run it from `task`, `orchestrate`, `groom` or any other pipeline, never on a feature commit, and never to provision a new server (that is the one-time setup in docs/deploy/vps.md).
disable-model-invocation: true
---

# deploy

Production runs one commit of `main` on one VPS. "Only a commit on `main` deploys" is enforced
twice: by this skill's checks and by `scripts/deploy-vps.sh`, which refuses any commit that is
not an ancestor of `origin/main`. The setup, the layout on the server and the manual operations
are in `docs/deploy/vps.md`. `DEPLOY_HOST` (the ssh target) must be set in the environment;
ask the human for it if it is not, never guess it.

## 1. Resolve what ships

```bash
git fetch origin
git log -1 --format='%H %s' origin/main
scripts/deploy-vps.sh --dry-run            # or --ref <commit> for a rollback
```

The dry run prints the commit, what is running now and the target URL. If both are the same
commit, say so and stop unless the human asked for a redeploy.

## 2. Check CI passed on that commit

`gh run list --branch main --workflow CI --limit 5 --json headSha,conclusion` must show a
`success` for the exact SHA. No green CI for that commit: stop and report.

## 3. Confirm, then deploy

State the plan back in one line (`<old> -> <new> on <url>`, migrations included if
`git diff --name-only <old> <new> -- backend/alembic/versions` lists any) and wait for the
human's yes. Then run it (in the background when the harness allows it; the build takes several
minutes):

```bash
scripts/deploy-vps.sh                      # or --ref <commit>
```

It builds from `git archive` (local edits never ship), streams the images over ssh, syncs
`deploy/vps/compose.yml` and `deploy/vps/Caddyfile`, bumps `APP_RELEASE`, waits for every
container to be healthy and reloads Caddy, so a Caddyfile-only change takes effect. The api
container runs `alembic upgrade head` on start.

## 4. Verify and report

The script already fails unless `/` and `/api/health` answer 200. Also run:

```bash
ssh "$DEPLOY_HOST" 'cd /opt/app && docker compose ps && docker compose logs api --since 5m | grep -E "\"level\": \"(ERROR|WARNING)\"" | tail -20'
```

Report the commit that went live (id and subject), the one it replaced, the migrations applied,
the curl results and any warning in the api log, quoted. Never report a deploy as done without
this output.

## Rollback

`scripts/deploy-vps.sh --ref <previous main commit>` redeploys an older commit. It is safe only
when no migration ran in between: a newer schema under an older api fails at startup or later.
With a migration in between, stop and ask; the fix is a forward commit through a PR, never
`alembic downgrade` on production without a backup.

## Never

- Deploy a commit that is not on `origin/main`, or edit the stack directory by hand to get
  around it.
- Print, copy or commit the server's `.env` or `.env.api`.
- Run `docker compose down -v` (it deletes the database volume).

## Harness notes

- **Claude Code** — `disable-model-invocation: true`: runs only when a human types `/deploy`.
  Run the build step with `run_in_background` and wait for its notification.
- **Codex** — invoked as `$deploy`. Codex reads only `name` and `description`, so the
  "human-invoked only" constraint lives in the description; confirm the plan before step 3.
