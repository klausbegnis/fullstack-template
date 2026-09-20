#!/bin/sh
set -u

root=$(git rev-parse --show-toplevel 2>/dev/null) || root=$(pwd)
hooks="$root/.agents/hooks"

payload=$(cat)
[ -n "$payload" ] || exit 0

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf '%s' "$payload" >"$tmp/event.json"

files=$(python3 "$hooks/hook_io.py" paths <"$tmp/event.json" 2>/dev/null) || files=""
[ -n "$files" ] || exit 0

harness=$(python3 "$hooks/hook_io.py" harness <"$tmp/event.json" 2>/dev/null) || harness="claude"

py_files=$(printf '%s\n' "$files" | grep -E '^backend/.+\.py$' || true)
ts_files=$(printf '%s\n' "$files" | grep -E '^frontend/src/.+\.(ts|tsx)$' || true)
: >"$tmp/findings"

if [ -n "$py_files" ] && command -v uv >/dev/null 2>&1; then
  abs=$(printf '%s\n' "$py_files" | sed "s#^#$root/#")
  (cd "$root/backend" && uv run ruff format $abs) >/dev/null 2>&1 || true
  (cd "$root/backend" && uv run ruff check --fix $abs) >/dev/null 2>&1 || true
  if ! (cd "$root/backend" && uv run ruff check $abs) >"$tmp/ruff" 2>&1; then
    cat "$tmp/ruff" >>"$tmp/findings"
  fi
fi

if [ -n "$ts_files" ] && command -v npx >/dev/null 2>&1; then
  rel=$(printf '%s\n' "$ts_files" | sed 's#^frontend/##')
  (cd "$root/frontend" && npx --no-install prettier --write $rel) >/dev/null 2>&1 || true
  (cd "$root/frontend" && npx --no-install eslint --fix $rel) >/dev/null 2>&1 || true
  if ! (cd "$root/frontend" && npx --no-install eslint $rel) >"$tmp/eslint" 2>&1; then
    cat "$tmp/eslint" >>"$tmp/findings"
  fi
fi

[ -s "$tmp/findings" ] || exit 0

if [ "$harness" = "codex" ]; then
  python3 "$hooks/rules_for_path.py" $files >"$tmp/context" 2>/dev/null || : >"$tmp/context"
  python3 "$hooks/hook_io.py" post-block \
    --reason-file "$tmp/findings" --context-file "$tmp/context"
  exit 0
fi

cat "$tmp/findings" >&2
exit 2
