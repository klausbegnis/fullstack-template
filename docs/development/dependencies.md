# Dependencies: scanning and updates

## What is locked

| Area | Lockfile | Versions in the manifest |
|---|---|---|
| Backend | `backend/uv.lock` | ranges in `pyproject.toml`; the lock pins exact versions and hashes |
| Frontend | `frontend/package-lock.json` | exact versions; `overrides` patch vulnerable transitive packages |
| E2E | `e2e/package-lock.json` | exact versions |
| Images | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | tag plus `@sha256:` digest |
| CI actions | `.github/workflows/*.yml` | full commit SHA |

The backend image installs from `uv export --frozen` with `pip install --require-hashes`, so a
build cannot pick up a package the lock does not name.

## Scanning: `scripts/audit-deps.sh`

One command runs every scanner and prints a one-line verdict per tool:

```bash
scripts/audit-deps.sh             # report only, exit 0
scripts/audit-deps.sh --strict    # exit 1 on any HIGH or CRITICAL finding
scripts/audit-deps.sh --images    # also build and scan the api and frontend images
scripts/audit-deps.sh --skip-trivy  # on a machine without Docker
```

| Tool | What it reads |
|---|---|
| `uv audit` | `backend/uv.lock` against OSV (it reports no severity, so `--strict` fails on any finding) |
| `npm audit` | every `package-lock.json` under `frontend/` and `e2e/` |
| `trivy fs` | every lockfile in the repo with dev dependencies included, committed secrets, and Dockerfile, compose and workflow misconfigurations |
| `trivy image` | with `--images`: the OS and language packages of the built images; findings with no fixed version are left out, since a base-image bump cannot patch them |

Trivy runs from a digest-pinned `aquasec/trivy` image rather than a GitHub Action, so CI and a
laptop run the same scanner. Its vulnerability database is cached in `~/.cache/trivy`. Full
reports go to `--out <dir>` (a temp directory by default).

### Accepting an advisory: `scripts/audit-deps.ignore`

One advisory per line, `<ID> <reason>`, reviewed in the PR that adds it. The reason says why the
vulnerable code is unreachable here and when to revisit. An ignored ID is excluded from every
tool's count; an npm package counts as ignored only when every advisory it carries, directly or
through its dependencies, is ignored.

## Updating

- **Backend:** `uv lock --upgrade-package <name>` for a targeted bump, `uv lock --upgrade` for
  everything, then `uv sync --locked` and the full backend suite with `DATABASE_URL` set.
- **Frontend:** edit the exact version in `package.json`, `npm install`, then typecheck, lint,
  test and build. A vulnerable transitive package with no fixed parent goes into `overrides`,
  pinned to the patched version. Never run `npm audit fix --force`: it moves packages across
  major versions.
- **Images:** change the tag and the digest together
  (`docker buildx imagetools inspect <image>:<tag>` prints the digest).

## CI

| Job | When | Command |
|---|---|---|
| Dependency audit | every non-draft PR and every push to `main` | `scripts/audit-deps.sh --strict` |
| Image audit | when a Dockerfile, compose file, workflow or lockfile changes, and on `main` | `scripts/audit-deps.sh --strict --images-only` |

Both upload their reports as a workflow artifact for 14 days.

## Update bot

`.github/dependabot.yml` opens weekly grouped PRs for Docker images, compose images, GitHub
Actions (as full commit SHAs), `uv` and `npm`. The frontend entry ignores `eslint` and
`eslint-config-next` major bumps, which need a coordinated config migration.
