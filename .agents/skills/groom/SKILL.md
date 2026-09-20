---
name: groom
description: Turn a product idea or rough notes into a reviewed repository PRD and executable GitHub issues. Use when asked to groom an idea, write a PRD, or break a product proposal into issues; not for implementation or review.
---

# Groom a product idea

Resolve the repository root with `git rev-parse --show-toplevel`. Read root-relative
`AGENTS.md`, `CONTRIBUTING.md`, `docs/prds/README.md`, and the current
`.claude/skills/groom/SKILL.md` before starting. The Claude skill is the maintained
source for the PRD template, issue headings, decomposition rules, and gate semantics.
Use those repository contracts, adapting Claude-only commands and tools to the
current Codex environment. Do not execute `Agent`, todo-tool, model, or slash-command
instructions literally.

Produce a PRD under `docs/prds/`, open it for review, then create issues from its
work breakdown at the gate specified by the user. The user may authorize the full
flow in the request; do not ask again for an action already authorized. Respect a
requested dry run. Keep each issue's headings exactly compatible with the forms in
`.github/ISSUE_TEMPLATE/` and the task parser contract. Report the PRD, issues,
and any gate that still needs a decision.
