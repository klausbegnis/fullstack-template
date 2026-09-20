#!/bin/sh
set -u

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
hooks="$root/.agents/hooks"

payload=$(cat 2>/dev/null) || payload=""

if [ -n "$payload" ]; then
  active=$(printf '%s' "$payload" | python3 "$hooks/hook_io.py" field stop_hook_active 2>/dev/null) || active=""
  [ -z "$active" ] || exit 0
fi

cd "$root"
[ -n "$(git status --porcelain)" ] || exit 0

if output=$("$hooks/changed_checks.sh" dirty 2>&1); then
  exit 0
fi

printf '%s\n' "$output" >&2
printf '\nThe worktree is dirty and its change-scoped checks are red. A check you did not pass is not a check you can report. Fix the failures above before finishing.\n' >&2
exit 2
