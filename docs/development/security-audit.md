# Security audit runs

`.agents/skills/security-audit/` is a pinned copy of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill). It runs
an agent-driven, source-first audit with these phases:

1. reconnaissance;
2. coverage-led hunting;
3. independent validation;
4. schema-checked findings;
5. a final fresh-eyes verification;
6. reports.

This page covers how to run it here and how to keep the copy current. The skill's own
`SKILL.md` ends with the repo overrides that win over upstream.

## Running a pass

Ask the agent explicitly, naming profile, scope and budget. For example, in Claude Code:

```text
/security-audit full audit, profile quick, scoped to <paths or "the diff since <ref>">,
strict budget 12 agent invocations, output ~/security-audit-skill/<repo-name>/run-<N>
```

- **Output** goes to `~/security-audit-skill/<repo-name>/run-<N>`, outside the repo and never
  committed. It contains:
  - `REPORT.md`, `FINDINGS-DETAIL.md` and `NEEDS-VALIDATION.md`;
  - the machine records `findings.json` and `coverage-ledger.json`;
  - per-agent evidence under `agents/`.
- **Runs are additive.** A new run reads every earlier ledger in that directory. It
  re-verifies unchanged confirmations and turns deferred or `needs_validation` units into
  current work.
- **Execution** of target code happens only in
  `.agents/skills/security-audit/tools/sandbox-run.sh`, with no network and the repo read-only.
  It needs `bwrap`, a user systemd scope and the backend `.venv`. Without them the agents stay
  source-only.

## Cost and cadence

A `quick` run scoped to one surface used 11 agent invocations: 4 reconnaissance, 3 hunters,
1 critic and 3 verifiers. A `standard` run over the whole app is several times that.

| Pass | Scope | When |
|---|---|---|
| Diff pass | `quick`, scoped to the diff since the last run's `source_ref` | before each release |
| Surface pass | `quick`, one surface, rotating: auth/session/CSRF, each domain router, admin, file uploads and storage | monthly |
| Full pass | `standard`, whole repo | on owner approval, for example before a public launch |

A scheduled agent (`/schedule` in Claude Code) can run the diff pass. It must write to the
output directory only and file nothing on its own. Turning findings into issues stays a human
step.

## From findings to work

- **`confirmed`** becomes a `bug` issue labelled `security`, implemented through `task`. The
  issue links the run's `REPORT.md` section and quotes the verifier's observed result.
- **`needs_validation`** names an exact missing fact, usually about the deployment, for example
  the hostname layout or proxy headers. The owner checks it. If it holds, open an issue; if not,
  the next run records the rejection.
- **Hardening notes** are batched into a `chore` when worth it.


## Updating the vendored copy

The copy changes only through a reviewed PR:

1. Clone upstream and diff `skills/security-audit/` against `.agents/skills/security-audit/`.
2. Ignore the local differences, which are the `description` provenance, the trailing
   `## Repo overrides` and `## Harness notes` sections of `SKILL.md`, and `tools/`.
3. Copy the upstream files over and bump the commit SHA in the `description`.
4. Run `node --test .agents/skills/security-audit/*.test.cjs`.
5. Re-read the changed phase files before the next run. Changes to the schema or validators
   can invalidate earlier ledgers, which the skill then reports as incompatible prior runs.
