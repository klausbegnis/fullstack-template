---
paths:
  - ".agents/**"
  - ".claude/**"
  - ".codex/**"
  - ".github/**"
  - "docs/prds/**"
---

Rules for the agent harness itself: the issue and PRD contract the workflow skills parse, the
single-source layout both Claude Code and Codex read, how a rule file is written, and what a
reviewer agent is allowed to do.

### Treat issue headings, labels and PRD names as a machine contract

`groom` writes issue bodies and `task` parses them, so the headings rendered by
`.github/ISSUE_TEMPLATE/*.yml` — `What is it`, `Specs`, `Pre-exploration`,
`Acceptance criteria`, `Out of scope`, `Related documents`, `Area` — are strings both ends
agree on, as are the label names in `.github/labels.yml` and the `NNNN-slug.md` PRD filename.
Rename a field in a form and the parser keeps running against a section it can no longer read.

Enforced by: backend/tests/unit/architecture/test_repo_contracts.py

### Maintain every harness artefact once under `.agents/`

`.agents/` holds the real bodies — rules, skills, agent rubrics, hooks, scaffolds — and both
harnesses point at it: `.claude/rules` and `.claude/skills` are symlinks, `.claude/agents/*.md`
add only Claude frontmatter, `.codex/agents/*.toml` instruct the model to read
`.agents/agents/<name>.md`, and both `.claude/settings.json` and `.codex/hooks.json` reference
the same scripts under `.agents/hooks/`. Every `CLAUDE.md` in the tree is exactly `@AGENTS.md`
beside a real `AGENTS.md`. A second copy of any of these drifts within one change.

Enforced by: backend/tests/unit/architecture/test_repo_contracts.py

### Write a rule as heading, why, example pair and `Enforced by:`

The `###` heading is the rule, stated as an imperative; one to three sentences say why, with
the number when there is one; an `**Incorrect:**` block is always followed by a `**Correct:**`
block; the last line names the mechanism that catches a violation. Headings are unique across
every rule file and no rule is stated in two files — rule-file load order is undocumented, so a
duplicated rule is a contradiction waiting for a reader to pick a side.

Enforced by: backend/tests/unit/architecture/test_rules_contracts.py

### Scope every rule file with `paths:` that match real files

`paths:` is the only frontmatter key. It is a YAML list of repo-root-relative globs, and Claude
Code loads the file lazily when a matching path is read, which is what keeps the always-on
context small. A glob that matches nothing is a rule that never loads and nobody notices.

**Incorrect:**

```yaml
---
paths: "backend/app/**"
description: Backend layering rules
---
```

**Correct:**

```yaml
---
paths:
  - "backend/app/**"
---
```

Enforced by: backend/tests/unit/architecture/test_rules_contracts.py

### Keep reviewer agents read-only

A reviewer that can edit fixes what it finds instead of reporting it, and the finding never
reaches the diff under review. Claude rubrics declare `tools: Bash, Read, Grep, Glob`; the
Codex equivalents set `sandbox_mode = "read-only"`.

Enforced by: backend/tests/unit/architecture/test_repo_contracts.py

### Never claim a check passed unless it was run

Say what was run and quote its output. A test, an integration check, a recovery procedure or an
external call reported as green without being executed is worse than no report, because the
next person stops looking.

Enforced by: review

### Keep root `AGENTS.md` under 200 lines

It is loaded on every turn in both harnesses and survives compaction, so every line in it costs
context on work it does not apply to. It carries the stack table, the commands, the environment
preconditions, the rules index and the few rules that fail dangerously when missed; everything
scoped to a tree goes to a rule file.

Enforced by: backend/tests/unit/architecture/test_rules_contracts.py
