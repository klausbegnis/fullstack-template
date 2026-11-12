#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: deploy-vps.sh [--ref <commit>] [--dry-run] [--help]

Deploys a commit of origin/main to a single VPS (docs/deploy/vps.md):
  1. refuses any commit that is not on origin/main
  2. exports the commit with git archive, so local changes never ship
  3. builds the api and frontend images, tagged with the short commit id
  4. streams them to the VPS (docker save | ssh docker load)
  5. syncs deploy/vps/compose.yml and deploy/vps/Caddyfile to $DEPLOY_DIR,
     sets APP_RELEASE in $DEPLOY_DIR/.env, runs docker compose up --wait (the
     api container applies migrations on start) and reloads Caddy, whose
     container is not recreated when only the Caddyfile changed
  6. checks https://$SITE_ADDRESS/ and /api/health from outside

The VPS secrets ($DEPLOY_DIR/.env, $DEPLOY_DIR/.env.api) are never read or
written by this script except for the APP_RELEASE, STACK_NAME and SITE_ADDRESS
lines.

Options:
  --ref <commit>  Commit to deploy (default: origin/main). An older main
                  commit is a rollback; its migrations must still match the
                  database, see docs/deploy/vps.md.
  --dry-run       Resolve and check the commit, print the plan, deploy nothing.
  --help          Show this message.

Environment:
  DEPLOY_HOST     ssh target, for example deploy@203.0.113.10 (required)
  DEPLOY_DIR      stack directory on the VPS (default: /opt/app)
USAGE
}

DEPLOY_DIR="${DEPLOY_DIR:-/opt/app}"
REF="origin/main"
DRY_RUN=false

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="${2:?--ref needs a commit}"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "deploy: $*" >&2; exit 1; }

[ -n "${DEPLOY_HOST:-}" ] || die "set DEPLOY_HOST to the VPS ssh target, for example deploy@203.0.113.10"

ROOT=$(git rev-parse --show-toplevel)
git -C "$ROOT" fetch --quiet origin main
SHA=$(git -C "$ROOT" rev-parse --verify --quiet "$REF^{commit}") || die "unknown commit: $REF"
git -C "$ROOT" merge-base --is-ancestor "$SHA" origin/main \
  || die "$SHA is not on origin/main; only commits merged into main are deployed"
VERSION=$(git -C "$ROOT" rev-parse --short=8 "$SHA")

SSH=(ssh -o BatchMode=yes "$DEPLOY_HOST")
"${SSH[@]}" "test -f $DEPLOY_DIR/.env && test -f $DEPLOY_DIR/.env.api" \
  || die "$DEPLOY_HOST:$DEPLOY_DIR is not provisioned (see docs/deploy/vps.md, One-time setup)"
remote_env() { "${SSH[@]}" "grep '^$1=' $DEPLOY_DIR/.env | cut -d= -f2-" || true; }
SITE=$(remote_env SITE_ADDRESS)
STACK=$(remote_env STACK_NAME)
STACK=${STACK:-app}
CURRENT=$(remote_env APP_RELEASE)

echo "deploy: $VERSION ($(git -C "$ROOT" log -1 --format=%s "$SHA"))"
echo "deploy: running now: ${CURRENT:-nothing}"
echo "deploy: target: $DEPLOY_HOST:$DEPLOY_DIR ($STACK) -> https://$SITE"
$DRY_RUN && { echo "deploy: dry run, nothing changed"; exit 0; }

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
git -C "$ROOT" archive "$SHA" | tar -x -C "$BUILD"
docker build --quiet -t "$STACK-api:$VERSION" "$BUILD/backend" >/dev/null
docker build --quiet -t "$STACK-frontend:$VERSION" -f "$BUILD/frontend/Dockerfile" "$BUILD" >/dev/null
echo "deploy: images built"

docker save "$STACK-api:$VERSION" "$STACK-frontend:$VERSION" | gzip -1 \
  | "${SSH[@]}" "gunzip | docker load" >/dev/null
echo "deploy: images loaded on the VPS"

scp -q -o BatchMode=yes "$BUILD/deploy/vps/compose.yml" "$BUILD/deploy/vps/Caddyfile" "$DEPLOY_HOST:$DEPLOY_DIR/"
"${SSH[@]}" "cd $DEPLOY_DIR && sed -i 's/^APP_RELEASE=.*/APP_RELEASE=$VERSION/' .env \
  && docker compose up -d --wait --wait-timeout 300 --remove-orphans >/dev/null \
  && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
  && docker compose ps --format '{{.Service}} {{.Status}}'"

curl -fsS -o /dev/null "https://$SITE/" || die "https://$SITE/ did not answer 200"
curl -fsS -o /dev/null "https://$SITE/api/health" || die "https://$SITE/api/health did not answer 200"
echo "deploy: $VERSION is live on https://$SITE (was ${CURRENT:-nothing})"

"${SSH[@]}" "docker image prune -af --filter 'until=168h' >/dev/null" || true
