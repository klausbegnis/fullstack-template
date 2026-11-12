#!/bin/bash
set -euo pipefail

usage() {
  echo "usage: sandbox-run.sh <audit-root>/<repo>/run-<N>/agents/<agent-id>/scratch -- <command...>" >&2
  exit 2
}

[ "$#" -ge 3 ] || usage
SCRATCH="$(readlink -f "$1")"
shift
[ "$1" = "--" ] || usage
shift

AUDIT_ROOT="$(readlink -f "${SECURITY_AUDIT_ROOT:-$HOME/security-audit-skill}")"
case "$SCRATCH" in
  "$AUDIT_ROOT"/*/run-*/agents/*/scratch) ;;
  *) echo "scratch must live under $AUDIT_ROOT/<repo>/run-<N>/agents/<agent-id>/scratch" >&2; exit 2 ;;
esac
mkdir -p "$SCRATCH/home" "$SCRATCH/tmp" "$SCRATCH/cache"

TARGET="$(git -C "$(dirname "$(readlink -f "$0")")" rev-parse --show-toplevel)"
PYTHON_INSTALLS="$(dirname "$(dirname "$(dirname "$(readlink -f "$TARGET/backend/.venv/bin/python")")")")"
NODE_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v node)")")")"

MASKS=()
for secret in "$TARGET/.env" "$TARGET/backend/.env" "$TARGET"/frontend/.env*; do
  case "$secret" in *.example) continue ;; esac
  [ -e "$secret" ] && MASKS+=(--ro-bind /dev/null "$secret")
done

exec systemd-run --user --scope --quiet -p TasksMax=256 -p MemoryMax=4G -p CPUQuota=200% -- \
  prlimit --fsize=67108864 --cpu=300 --nofile=1024 -- \
  timeout --kill-after=5 300 \
  bwrap --unshare-all --die-with-parent --new-session \
    --ro-bind /usr /usr --ro-bind /etc /etc \
    --ro-bind-try /lib /lib --ro-bind-try /lib64 /lib64 --ro-bind-try /bin /bin --ro-bind-try /sbin /sbin \
    --proc /proc --dev /dev --tmpfs /tmp --tmpfs /home \
    --ro-bind "$PYTHON_INSTALLS" "$PYTHON_INSTALLS" \
    --ro-bind "$NODE_HOME" "$NODE_HOME" \
    --ro-bind "$TARGET" "$TARGET" \
    "${MASKS[@]}" \
    --bind "$SCRATCH" "$SCRATCH" \
    --clearenv \
    --setenv HOME "$SCRATCH/home" --setenv TMPDIR "$SCRATCH/tmp" --setenv XDG_CACHE_HOME "$SCRATCH/cache" \
    --setenv PATH "$TARGET/backend/.venv/bin:$NODE_HOME/bin:/usr/bin:/bin" \
    --setenv TESTING true --setenv PYTHONDONTWRITEBYTECODE 1 \
    --chdir "$SCRATCH" "$@"
