# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/klausbegnis/fullstack-template/security/advisories/new)
rather than in a public issue or pull request. Include the affected files or endpoints, the
steps to reproduce, and the impact you observed. You should get a first reply within a week.

## Supported versions

Only the latest commit on `main` is supported. This is a template: once you create a project
from it, applying fixes to your copy is up to you. Watch this repository's security advisories
and Dependabot updates to hear about fixes worth porting.

## What is in scope

The backend auth and session handling, the frontend session renewal and Content Security
Policy, the container images and compose files, the CI workflows and the deploy kit in
`deploy/`. Findings in vendored third-party material (see `THIRD_PARTY_NOTICES.md`) are best
reported upstream as well.

## Hardening already in place

See the Security row of the README and `docs/architecture/backend.md` for what the template
already does (Origin checks on cookie-authenticated mutations, Postgres-backed login rate
limits, an audit log, idle and absolute session lifetimes, a nonce-based CSP), and
`docs/development/dependencies.md` for how dependencies are scanned.
