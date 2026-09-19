#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: sync-labels.sh [--repo <owner/name>] [--dry-run] [--prune] [--force] [--help]

Syncs GitHub issue labels from .github/labels.yml onto a repository: creates
labels that are missing and updates the colour/description of labels that
already exist. Safe to re-run.

Options:
  --repo <owner/name>  Target repository. Defaults to the repository resolved
                        by "gh repo view --json nameWithOwner".
  --dry-run            Print what would change without changing anything.
  --prune              Delete remote labels that are absent from labels.yml.
                        Off by default. Refuses to delete a label that has
                        issues attached unless --force is also given.
  --force              Allow --prune to delete a label that has issues attached.
  --help               Show this help message.
USAGE
}

REPO=""
DRY_RUN=false
PRUNE=false
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      if [[ -z "$REPO" ]]; then
        echo "--repo requires a value" >&2
        exit 1
      fi
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --prune)
      PRUNE=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LABELS_FILE="$REPO_ROOT/.github/labels.yml"

if [[ ! -f "$LABELS_FILE" ]]; then
  echo "Labels file not found: $LABELS_FILE" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "The gh CLI is required. Install it from https://cli.github.com/" >&2
  exit 1
fi

if ! python3 -c "import yaml" >/dev/null 2>&1; then
  echo "python3 module 'yaml' (pyyaml) is required to parse $LABELS_FILE." >&2
  echo "Install it with: pip install --user pyyaml" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi

LABELS_TSV="$(python3 -c '
import sys
import yaml

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

for entry in data["labels"]:
    name = entry["name"]
    color = str(entry["color"]).lstrip("#")
    description = entry.get("description") or ""
    row = "\t".join([name, color, description])
    print(row.replace("\n", " "))
' "$LABELS_FILE")"

declare -A DESIRED_COLOR
declare -A DESIRED_DESC
DESIRED_NAMES=()

while IFS=$'\t' read -r name color description; do
  [[ -z "$name" ]] && continue
  DESIRED_NAMES+=("$name")
  DESIRED_COLOR["$name"]="$color"
  DESIRED_DESC["$name"]="$description"
done <<< "$LABELS_TSV"

EXISTING_TSV="$(gh api "repos/$REPO/labels" --paginate --jq '.[] | [.name, .color, (.description // "")] | @tsv')"

declare -A EXISTING_COLOR
declare -A EXISTING_DESC
EXISTING_NAMES=()

while IFS=$'\t' read -r name color description; do
  [[ -z "$name" ]] && continue
  EXISTING_NAMES+=("$name")
  EXISTING_COLOR["$name"]="$color"
  EXISTING_DESC["$name"]="$description"
done <<< "$EXISTING_TSV"

is_desired() {
  local target="$1"
  local n
  for n in "${DESIRED_NAMES[@]}"; do
    [[ "$n" == "$target" ]] && return 0
  done
  return 1
}

is_existing() {
  local target="$1"
  local n
  for n in "${EXISTING_NAMES[@]}"; do
    [[ "$n" == "$target" ]] && return 0
  done
  return 1
}

for name in "${DESIRED_NAMES[@]}"; do
  color="${DESIRED_COLOR[$name]}"
  description="${DESIRED_DESC[$name]}"
  if is_existing "$name"; then
    if [[ "${EXISTING_COLOR[$name]}" != "$color" || "${EXISTING_DESC[$name]}" != "$description" ]]; then
      if $DRY_RUN; then
        echo "would update label: $name"
      else
        gh api "repos/$REPO/labels/$name" -X PATCH -f "new_name=$name" -f "color=$color" -f "description=$description" >/dev/null
        echo "updated label: $name"
      fi
    fi
  else
    if $DRY_RUN; then
      echo "would create label: $name"
    else
      gh api "repos/$REPO/labels" -X POST -f "name=$name" -f "color=$color" -f "description=$description" >/dev/null
      echo "created label: $name"
    fi
  fi
done

if $PRUNE; then
  for name in "${EXISTING_NAMES[@]}"; do
    if ! is_desired "$name"; then
      ISSUE_COUNT="$(gh api "repos/$REPO/issues?labels=$name&state=all&per_page=1" --jq 'length')"
      if [[ "$ISSUE_COUNT" != "0" && "$FORCE" != true ]]; then
        echo "skipping delete of '$name': it has issues attached, pass --force to delete anyway" >&2
        continue
      fi
      if $DRY_RUN; then
        echo "would delete label: $name"
      else
        gh api "repos/$REPO/labels/$name" -X DELETE >/dev/null
        echo "deleted label: $name"
      fi
    fi
  done
fi
