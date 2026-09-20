---
name: task
description: Deliver one implementation issue or described change through a worktree, checks, review, QA, and a pull request. Use for an end-to-end change; not for a question or a standalone code review.
---

# Deliver one task

Read root `AGENTS.md`, `CONTRIBUTING.md`, and `.claude/skills/task/SKILL.md`.
The Claude skill maintains the issue-body contract, branch naming, task record,
review criteria, and QA gate. Apply those durable rules with Codex tools. Adapt
Claude-only `Agent` calls, model choices, todo-tool commands, and slash-command
syntax to the current environment; they are not portable instructions.

For an issue, verify its state, labels, required sections, and related paths
before implementation. Use an isolated worktree and the documented issue branch
name. Record a concrete plan, implement it, run relevant repository checks,
review the changed paths against the maintained reviewer rubrics, and run the
isolated QA phase in `.claude/skills/task/qa-phase.md` with checks suited to the
change. Open a draft PR with the plan, evidence, and `Closes #<issue>`; mark it
ready only when the checks and QA gate pass.
Follow explicit user gate preferences and existing authorization. Treat missing
evidence as unverified and report any blocker with the next action.
