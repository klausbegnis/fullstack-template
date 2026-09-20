---
name: orchestrate
description: Coordinate an eligible backlog of multiple implementation tasks with bounded concurrency, dependencies, and isolated worktrees. Use for batches or agent-ready issues; use task for one change.
---

# Coordinate a backlog

Read root `AGENTS.md`, `CONTRIBUTING.md`, `.claude/skills/orchestrate/SKILL.md`,
and `.agents/skills/task/SKILL.md`. The Claude orchestration skill maintains the
eligibility filter, dependency and overlap rules, run-state format, and issue
status contract. Apply those shared decisions with available Codex tools; adapt
Claude-only agent calls, model assignments, and slash-command syntax.

Select only eligible work items. Track dependencies and overlapping files before
dispatch. Serialize migration changes so Alembic keeps one head. Bound concurrent
tasks to the actual agent capacity, give every task its own worktree and state,
and run each through the task workflow. Persist resumable run status and report
each issue's PR, gate, checks, and blocker. Do not merge pull requests unless the
user has authorized merging.
