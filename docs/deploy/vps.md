# Production deploy (single VPS)

An optional, minimal way to run this template in production: one Linux VPS with Docker, running
the same containers as `docker-compose.yml` behind Caddy, which gets and renews the TLS
certificate. Only a commit on `main` is ever deployed, and only through `scripts/deploy-vps.sh`
(by hand with the `deploy` skill, or from `.github/workflows/deploy.yml` once you enable it).
Nothing here runs until you set it up; delete `deploy/`, `scripts/deploy-vps.sh`,
`.github/workflows/deploy.yml` and `.agents/skills/deploy/` if you deploy some other way.

| | |
|---|---|
| Stack directory | `/opt/app` on the VPS (`DEPLOY_DIR`) |
| Files from the repo | `deploy/vps/compose.yml`, `deploy/vps/Caddyfile` (copied on every deploy); `deploy/vps/backup/*` (installed once) |
| Files only on the server | `/opt/app/.env`, `/opt/app/.env.api`, `/etc/default/app-backup` (mode 600, never in git) |

## What runs

```text
internet ─▶ :80/:443 caddy ─▶ frontend:3000 (next start) ─/api/*─▶ api:8000 ─▶ db:5432
```

- **caddy** is the only container that publishes ports. It redirects HTTP to HTTPS, sets HSTS
  for a year with `includeSubDomains` (without `preload`), a deny-by-default
  `Permissions-Policy`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, and a default
  `Referrer-Policy` written as `?Referrer-Policy` so a route's own policy wins. It overwrites
  `X-Real-IP` with the peer it saw, which the api can use as the client address for per-IP
  rate limits.
- **frontend** proxies `/api/*` to the api through the Next rewrite, exactly as in development;
  the api is never reachable from outside.
- **api** runs `alembic upgrade head` on every start (`backend/entrypoint.sh`), then serves with
  `ENVIRONMENT=production` (no `/docs`, no `DEBUG`) and `AUTH_COOKIE_SECURE=true`.
- **db** keeps its data in the `<stack>_postgres_data` volume.
- **Every container** drops all Linux capabilities (caddy keeps `NET_BIND_SERVICE`), runs with
  `no-new-privileges`, a memory and a pid limit, and, except `db`, a read-only root filesystem
  with a `/tmp` tmpfs. The api runs as uid 10001 and the frontend as `node` (uid 1000), both set
  in their Dockerfiles; `db` runs as `postgres` (uid 70).

Images are built on the deploying machine and streamed with `docker save | ssh docker load`, so
a small VPS never runs `next build` next to the live stack. They are tagged with the short
commit id, which `APP_RELEASE` in `/opt/app/.env` points at.

## Deploy

```bash
export DEPLOY_HOST=deploy@203.0.113.10
scripts/deploy-vps.sh --dry-run    # commit, what runs now, target URL
scripts/deploy-vps.sh              # origin/main
scripts/deploy-vps.sh --ref <sha>  # a specific main commit (rollback)
```

The script refuses a commit that is not an ancestor of `origin/main`, builds from `git archive`
(uncommitted edits never ship), waits until every container is healthy and fails unless `/` and
`/api/health` answer 200 from outside.

**Rollback** is a deploy of an older `main` commit, and it is safe only when no migration ran in
between. The schema never goes back automatically; with a migration in between, ship a fix
forward.

**GitHub Actions** (`.github/workflows/deploy.yml`) runs the same script on every push to `main`
once the repository variable `VPS_DEPLOY_ENABLED` is `true`. It also needs the variable
`VPS_DEPLOY_HOST` (the ssh target), optionally `VPS_DEPLOY_DIR`, and the secrets `VPS_SSH_KEY`
(a private key used only for deploys, its public half in the deploy user's
`authorized_keys`) and `VPS_KNOWN_HOSTS` (`ssh-keyscan <host>`), in a `production` environment.

## One-time setup

1. **A VPS** with Docker Engine and the Compose plugin (any Ubuntu LTS image with Docker works),
   and your deploy key in the deploy user's `authorized_keys`. Point DNS at it: `A @ -> <ip>`,
   `CNAME www -> <domain>`. Until you have a domain, `<ip with dashes>.sslip.io` resolves to the
   IP and gets a real certificate.
2. **Swap and firewall:**

   ```bash
   fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
   echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable
   ```

   Docker writes its own iptables rules and bypasses ufw for published ports, which is why
   `compose.yml` publishes nothing but caddy's 80/443. A provider-level firewall with the same
   four rules is a useful second layer.
3. **SSH with keys only.** `/etc/ssh/sshd_config.d/00-hardening.conf` (it must sort before any
   file that enables passwords, because sshd keeps the first value it reads):

   ```text
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PermitRootLogin prohibit-password
   PubkeyAuthentication yes
   ```

   Then `sshd -t && systemctl reload ssh`, and test a new key login before closing the session.
   Adding `fail2ban` with an `sshd` jail on the systemd backend is cheap and worth it.
4. **Stack directory and secrets**, generated on the server so they never cross the network:

   ```bash
   mkdir -p /opt/app && cd /opt/app
   # copy deploy/vps/.env.example and deploy/vps/.env.api.example here first
   gen() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
   SITE=example.com
   umask 077
   sed -e "s|__SITE__|$SITE|" -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen 24)|" .env.example > .env
   sed -e "s|__generated__|$(gen 48)|" -e "s|__SITE__|$SITE|g" .env.api.example > .env.api
   ```

   Every other backend setting (rate limits, alerts, ...) goes into `.env.api`; see
   `backend/.env.example` for the full list.
5. **First deploy:** `scripts/deploy-vps.sh` from your machine.
6. **First admin**, typed by the person who owns it (the password is prompted, never echoed):

   ```bash
   ssh -t "$DEPLOY_HOST" 'cd /opt/app && docker compose exec api python -m app.commands.bootstrap_admin <email> --yes'
   ```

## Operations

| Task | Command (on the VPS, in `/opt/app`) |
|---|---|
| State | `docker compose ps` |
| Logs | `docker compose logs api --since 30m` (JSON lines; `frontend`, `caddy` likewise) |
| Change a setting | edit `.env.api`, then `docker compose up -d api` |
| Resources | `free -h`, `docker stats --no-stream`, `df -h /` |

## Backups

`deploy/vps/backup/app-backup` dumps the database (`pg_dump -Fc`, taken inside the `db`
container) and tars the stack's configuration into `/var/backups/app/<UTC stamp>/` with a
`SHA256SUMS` file, keeps 14 days locally and, when `BACKUP_REMOTE` names an
[rclone](https://rclone.org) remote, copies each run there, verifies it and keeps 30 days.
Use an rclone `crypt` remote so the storage provider only ever sees encrypted names and
contents, and keep the crypt password and salt in a password manager: without them a lost VPS
means unreadable backups.

```bash
apt-get install -y rclone
install -m 700 deploy/vps/backup/app-backup /usr/local/sbin/app-backup
install -m 644 deploy/vps/backup/app-backup.{service,timer} /etc/systemd/system/
printf 'STACK_DIR=/opt/app\nBACKUP_REMOTE=offsite-crypt:daily\n' > /etc/default/app-backup
chmod 600 /etc/default/app-backup
systemctl daemon-reload && systemctl enable --now app-backup.timer && systemctl start app-backup.service
journalctl -u app-backup.service -n 20 -o cat   # a good run ends with "backup ok: <stamp>"
```

**Restore:** copy a run back (`rclone copy <remote>/<stamp> ./restore`), check it
(`sha256sum -c SHA256SUMS`), then `pg_restore -U <user> -d <db> --clean --if-exists --no-owner
db.dump` into a database with the api stopped, and untar `config.tar.gz` into the stack
directory. Rehearse a restore into a throwaway `postgres:16-alpine` container once, before you
need it.

## Not covered

- A separate, least-privilege database role for the api (the api connects as the database
  owner, which also runs the migrations).
- Object storage, email delivery, a CDN or a second server.
- Alerting on a failed backup: a failed run shows up only as a failed `app-backup.service` in
  the journal.
