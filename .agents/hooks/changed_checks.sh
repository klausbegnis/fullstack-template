#!/bin/sh
set -eu

mode=${1:-staged}

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

case "$mode" in
  staged)
    changed=$(git diff --cached --name-only --diff-filter=ACMR)
    ;;
  dirty)
    changed=$(git status --porcelain | sed 's/^...//' | sed 's/.* -> //')
    ;;
  *)
    echo "changed_checks.sh: unknown mode '$mode' (expected staged or dirty)" >&2
    exit 64
    ;;
esac

if [ -z "$changed" ]; then
  exit 0
fi

backend_changed=$(printf '%s\n' "$changed" | grep -c '^backend/' || true)
frontend_changed=$(printf '%s\n' "$changed" | grep -c '^frontend/' || true)
harness_changed=$(printf '%s\n' "$changed" | grep -cE '^(\.github|\.githooks|\.claude|\.agents|\.codex|docs/prds|scripts)/' || true)

if [ "$frontend_changed" -gt 0 ]; then
  python3 .agents/skills/task/scripts/task_env.py node
fi

if [ "$backend_changed" -gt 0 ]; then
  echo "checks: backend"
  uv run --directory backend ruff format --check .
  uv run --directory backend ruff check .
else
  echo "checks: backend unchanged, skipped"
fi

if [ "$frontend_changed" -gt 0 ]; then
  echo "checks: frontend"
  frontend_files=$(printf '%s\n' "$changed" | sed -n 's|^frontend/||p' | while IFS= read -r path; do
    if [ -f "frontend/$path" ]; then printf '%s\n' "$path"; fi
  done)
  lint_files=$(printf '%s\n' "$frontend_files" | grep -E '\.(ts|tsx|js|jsx|mjs|cjs)$' || true)
  if [ -n "$frontend_files" ]; then
    printf '%s\n' "$frontend_files" | xargs npm run --silent --prefix frontend format:files --
  fi
  if [ -n "$lint_files" ]; then
    printf '%s\n' "$lint_files" | xargs npm run --silent --prefix frontend lint:files --
  fi
else
  echo "checks: frontend unchanged, skipped"
fi

if [ "$harness_changed" -gt 0 ]; then
  echo "checks: harness contracts"
  python3 .agents/skills/task/scripts/test_task_env.py
  python3 .agents/hooks/test_hooks.py
  python3 .agents/scaffold/test_validate_scaffold.py
  if [ "$backend_changed" -eq 0 ]; then
    uv run --directory backend pytest tests/unit/architecture/test_repo_contracts.py -q
  fi
fi
