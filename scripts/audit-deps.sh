#!/usr/bin/env bash
set -uo pipefail

TRIVY_IMAGE="aquasec/trivy:0.75.0@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa"

usage() {
  cat <<'USAGE'
Usage: audit-deps.sh [--strict] [--skip-trivy] [--images] [--images-only] [--out <dir>] [--help]

Scans the locked dependency trees for known vulnerabilities:
  uv audit   backend/uv.lock against OSV
  npm audit  every package-lock.json under frontend/ and e2e/
  trivy      every lockfile in the repo, dev dependencies included, plus
             committed secrets and Dockerfile/compose/workflow misconfigurations,
             through a digest-pinned container image (needs docker; the
             vulnerability DB is cached in ~/.cache/trivy)
  trivy image  with --images: builds the api (backend/Dockerfile) and frontend
             (frontend/Dockerfile) images from this checkout and scans their
             OS and language packages; findings with no fixed version are
             left out (--ignore-unfixed), since a base image cannot patch them

Each tool's full report is written to --out (default: a new temp directory)
and a one-line verdict per tool is printed.

Advisories listed in scripts/audit-deps.ignore (one "<ID> <reason>" per line,
reviewed in the PR that adds them) are excluded from every count; a package is
excluded only when every advisory it carries, directly or through its
dependencies, is ignored.

Options:
  --strict      Exit 1 when any tool reports a HIGH or CRITICAL vulnerability
                (uv audit: any vulnerability, it reports no severity).
                Without it the script only reports and exits 0.
  --skip-trivy  Do not run trivy (for a machine without docker).
  --images      Also build and scan the api and frontend images.
  --images-only Build and scan the images only; skip the lockfile scanners.
  --out <dir>   Directory for the per-tool reports.
  --help        Show this message.
USAGE
}

strict=false
skip_trivy=false
scan_images=false
scan_lockfiles=true
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --strict) strict=true ;;
    --skip-trivy) skip_trivy=true ;;
    --images) scan_images=true ;;
    --images-only) scan_images=true; scan_lockfiles=false ;;
    --out) out="${2:?--out needs a directory}"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="${out:-$(mktemp -d -t audit-deps.XXXXXX)}"
mkdir -p "$out"
out="$(cd "$out" && pwd)"
failed=false

ignore_file="$root/scripts/audit-deps.ignore"
ignored_ids=()
if [ -f "$ignore_file" ]; then
  while read -r id _; do
    case "$id" in ""|\#*) continue ;; esac
    ignored_ids+=("$id")
  done < "$ignore_file"
fi
printf '%s\n' ${ignored_ids[@]+"${ignored_ids[@]}"} > "$out/ignored-ids.txt"

verdict() {
  local tool=$1 blocking=$2 summary=$3
  echo "$tool: $summary"
  [ "$blocking" = true ] && failed=true
}

run_uv_audit() {
  local ignore_args=() id
  for id in ${ignored_ids[@]+"${ignored_ids[@]}"}; do ignore_args+=(--ignore "$id"); done
  (cd "$root/backend" && uv audit --frozen --preview-features audit-command ${ignore_args[@]+"${ignore_args[@]}"}) > "$out/uv-audit.txt" 2>&1
  local rc=$? found
  found=$(grep -oE 'Found [0-9]+ known vulnerabilit(y|ies)' "$out/uv-audit.txt" | head -1)
  if [ $rc -eq 0 ]; then
    verdict "uv audit" false "clean"
  elif [ -n "$found" ]; then
    verdict "uv audit" "$strict" "${found#Found } (backend/uv.lock)"
  else
    verdict "uv audit" true "error (exit $rc), see $out/uv-audit.txt"
  fi
}

run_npm_audit() {
  local dir=$1 rc counts high
  (cd "$root/$dir" && npm audit --json) > "$out/npm-audit-$dir.json" 2> "$out/npm-audit-$dir.err"
  rc=$?
  counts=$(node -e '
    const fs = require("fs");
    const report = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
    const ignored = new Set(fs.readFileSync(process.argv[2], "utf8").split("\n").filter(Boolean));
    const packages = report.vulnerabilities;
    if (!packages) { process.exit(3); }
    const advisoryIgnored = (advisory) => [...ignored].some((id) => (advisory.url || "").endsWith(id));
    const memo = new Map();
    const fullyIgnored = (name, seen = new Set()) => {
      if (memo.has(name)) return memo.get(name);
      if (seen.has(name)) return true;
      seen.add(name);
      const via = (packages[name] || { via: [] }).via;
      const result = via.length > 0 && via.every((entry) =>
        typeof entry === "string" ? fullyIgnored(entry, seen) : advisoryIgnored(entry));
      memo.set(name, result);
      return result;
    };
    const tally = { critical: 0, high: 0, moderate: 0, low: 0, ignored: 0 };
    for (const [name, entry] of Object.entries(packages)) {
      if (fullyIgnored(name)) tally.ignored += 1;
      else if (entry.severity in tally) tally[entry.severity] += 1;
    }
    console.log(`${tally.critical} ${tally.high} ${tally.moderate} ${tally.low} ${tally.ignored}`);
  ' "$out/npm-audit-$dir.json" "$out/ignored-ids.txt") || { verdict "npm audit $dir" true "error (exit $rc), see $out/npm-audit-$dir.err"; return; }
  local critical high_count moderate low ignored
  read -r critical high_count moderate low ignored <<<"$counts"
  high=$((critical + high_count))
  local summary="$critical critical, $high_count high, $moderate moderate, $low low ($ignored ignored)"
  if [ "$high" -gt 0 ]; then
    verdict "npm audit $dir" "$strict" "$summary"
  else
    verdict "npm audit $dir" false "$summary"
  fi
}

trivy_scan() {
  local label=$1 report=$2 scope=$3
  shift 3
  if ! command -v docker >/dev/null 2>&1; then
    verdict "$label" true "docker not found (use --skip-trivy to run without it)"
    return
  fi
  mkdir -p "$HOME/.cache/trivy"
  docker run --rm \
    -v "$root:/src:ro" -v "$HOME/.cache/trivy:/root/.cache/trivy" -v "$out/ignored-ids.txt:/ignored-ids.txt:ro" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    "$TRIVY_IMAGE" "$@" --quiet --ignorefile /ignored-ids.txt \
    --format json --output /dev/stdout > "$out/$report.json" 2> "$out/$report.err"
  local rc=$? counts high
  counts=$(node -e '
    const report = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
    const tally = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 };
    const count = (severity) => { tally[severity] = (tally[severity] || 0) + 1; };
    for (const result of report.Results || []) {
      for (const vuln of result.Vulnerabilities || []) count(vuln.Severity);
      for (const secret of result.Secrets || []) count(secret.Severity);
      for (const misconfig of result.Misconfigurations || []) {
        if (misconfig.Status === "FAIL") count(misconfig.Severity);
      }
    }
    console.log(`${tally.CRITICAL} ${tally.HIGH} ${tally.MEDIUM} ${tally.LOW}`);
  ' "$out/$report.json") || { verdict "$label" true "error (exit $rc), see $out/$report.err"; return; }
  local critical high_count medium low
  read -r critical high_count medium low <<<"$counts"
  high=$((critical + high_count))
  local summary="$critical critical, $high_count high, $medium medium, $low low ($scope)"
  if [ "$high" -gt 0 ]; then
    verdict "$label" "$strict" "$summary"
  else
    verdict "$label" false "$summary"
  fi
}

run_trivy_fs() {
  trivy_scan "trivy" "trivy" "lockfiles, secrets, misconfigurations" fs --include-dev-deps \
    --scanners vuln,secret,misconfig \
    --skip-dirs '**/node_modules' --skip-dirs '**/.venv' --skip-dirs '**/.next' /src
}

build_image() {
  local name=$1 tag=$2
  shift 2
  if docker build -t "$tag" "$@" > "$out/build-$name.log" 2>&1; then
    return 0
  fi
  verdict "trivy image $name" true "image build failed, see $out/build-$name.log"
  return 1
}

run_trivy_images() {
  local revision api_tag frontend_tag
  revision="$(git -C "$root" rev-parse --short=12 HEAD)"
  api_tag="app-audit/api:$revision"
  frontend_tag="app-audit/frontend:$revision"
  if build_image api "$api_tag" "$root/backend"; then
    trivy_scan "trivy image api" "trivy-image-api" "$api_tag" image --scanners vuln --ignore-unfixed "$api_tag"
  fi
  if build_image frontend "$frontend_tag" -f "$root/frontend/Dockerfile" "$root"; then
    trivy_scan "trivy image frontend" "trivy-image-frontend" "$frontend_tag" image --scanners vuln --ignore-unfixed "$frontend_tag"
  fi
}

if [ "$scan_lockfiles" = true ]; then
  run_uv_audit
  for dir in frontend e2e; do
    [ -f "$root/$dir/package-lock.json" ] && run_npm_audit "$dir"
  done
  if [ "$skip_trivy" = true ]; then
    echo "trivy: skipped (--skip-trivy)"
  else
    run_trivy_fs
  fi
fi
if [ "$scan_images" = true ]; then
  if [ "$skip_trivy" = true ]; then
    echo "trivy image: skipped (--skip-trivy)"
  else
    run_trivy_images
  fi
fi
echo "reports: $out"

[ "$failed" = false ]
