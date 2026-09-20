# PRDs in this repository

A PRD is the durable **why and what** for a capability. It lives in the repo as a file under
`docs/prds/`, it is versioned with the code it describes, and it changes the same way the code
does: through a pull request, reviewed like any other diff.

An issue is a **unit of work**. It is transient: it is opened to do one bounded thing, it closes
when that thing is done, and it links back to the PRD it was spawned from through the `Related
documents` field. An issue answers "what should an agent do next"; a PRD answers "why does this
capability exist, and what does it need to do".

## Division of labour

A PRD is written once and refined over time, in place, through edits to the same file. Issues are
spawned from its `Work breakdown` table: the `/groom` skill reads a PRD, turns each row into a
GitHub issue using the templates in `.github/ISSUE_TEMPLATE/`, and writes the resulting issue
number back into the `Issue` column. `/task` then executes one issue at a time, reading its body
by the exact H3 headings the issue forms render and its `Related documents` field to pull in the
parent PRD for context. The PRD does not move; issues are produced from it and consumed by
execution.

## Why a PRD is not an issue

- An issue body is edited in place. There is no diff to review when its meaning changes, and no
  reviewer sees that it changed.
- An issue has no history you can bisect. `git blame` on a file tells you who changed a
  requirement and why; an issue's edit history is a flat audit log at best, and GitHub UI-only
  when the repo is not the source of truth.
- An issue is invisible to an agent working offline in a git worktree. A file under `docs/prds/`
  checks out with the branch; a GitHub issue requires a network call and a token an unattended
  agent may not have.
- An issue rots silently. Nothing forces its text to track a code change that invalidates it — it
  just sits there, stale, open or closed, until a human notices. A PRD living beside the code it
  describes is at least a candidate for the same review that touches that code, and a stale PRD
  section is a visible diff waiting to happen the next time someone edits the file.
- A file in `docs/prds/` is in every agent's context by construction: it is checked out with the
  repository, greppable, and readable without any tool beyond the filesystem. An issue is not.

## Why an issue is not a PRD

A PRD is not a queue: it has no assignee, no state machine beyond its own `Status:` line, and no
notification surface. It cannot tell anyone that it is waiting on them. Issues exist because work
needs exactly those things — someone to pick it up, a closed/open state that downstream tooling
(`/groom`, `/task`, project boards) can act on, and a place for review comments and CI status to
attach. Collapsing the two into one artifact would force every requirements document to also be a
mutable to-do item, which is what makes issues rot in the first place.

## Naming and numbering

- PRDs live at `docs/prds/<NNNN>-<kebab-slug>.md`, where `NNNN` is a zero-padded 4-digit number
  and `<kebab-slug>` is a short kebab-case description of the capability, e.g.
  `0001-user-management.md`.
- The H1 of every PRD file is `# PRD <NNNN>: <Title>`, `<Title>` being the human-readable name
  that matches the slug (e.g. `# PRD 0001: User management`).
- To pick the next number: list the files already in `docs/prds/`, take the highest `NNNN` among
  them, and increment by one. The first PRD in a repository is `0001`. Numbers are never reused,
  even for a PRD that is later superseded or abandoned.

## Sections

Every PRD uses the exact H2 section list and order defined in `docs/prds/TEMPLATE.md`, ending in a
`Work breakdown` table with the columns `Issue | Title | Area | Type | Depends on`. `Issue` starts
empty and is filled in by `/groom` with the number of the GitHub issue it creates for that row;
`Depends on` names other rows so `/groom` and a human reviewer can sequence the resulting issues.

## Lifecycle

Recorded in a `Status:` line directly under the H1, alongside `Owner:` and `Last updated:`:

1. **Draft** — being written or actively renegotiated. Not yet ready for `/groom` to spawn issues
   from it.
2. **Accepted** — the problem, goals, and requirements are settled. Issues may be groomed from its
   `Work breakdown` table.
3. **In progress** — at least one issue spawned from this PRD is open or merged, and the capability
   is not yet fully shipped.
4. **Shipped** — every row in `Work breakdown` is done and the capability described in `Problem`/
   `Goals` exists in the codebase as specified.
5. **Superseded** — replaced by a later PRD, which should be named in the `Status:` line as
   `Superseded by` followed by that PRD's path. A superseded PRD is left in place, not deleted:
   it is still the historical record of why the earlier shape existed.

A PRD only moves forward through this list via a pull request that edits its `Status:` line, same
as any other change to the file.
