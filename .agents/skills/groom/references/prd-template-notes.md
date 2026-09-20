# PRD writing notes

Checklist `/groom` consults at G2. One entry per H2 section, in the order the contract fixes.
Bad means: technically fills the section, tells the reader nothing they could act on.

## Problem

- Good: names who is affected, what breaks or costs them today, and why now, grounded in a
  `file:line` or a support/incident reference where one exists.
- Bad: restates the feature as a problem ("we lack password reset").
- Bad example: "Users cannot reset their password."
- Good example: "Support fields 12 manual password resets a week (backend/app/routers/auth.py
  has no reset flow); each one is a support ticket plus a direct DB update."

## Goals

- Good: outcomes checkable against the shipped result — a reviewer can look at the diff and
  say yes or no.
- Bad: restates goals as activities ("implement password reset").
- Bad example: "Add password reset."
- Good example: "A user who forgets their password can regain access without contacting
  support."

## Non-goals

- Good: excludes things a reader would otherwise assume are in scope, so silence later isn't
  mistaken for an oversight.
- Bad: a generic disclaimer that excludes nothing specific to this PRD.
- Bad example: "Out of scope: unrelated features."
- Good example: "Does not cover SSO-only accounts — they have no password to reset."

## Users and scenarios

- Good: concrete enough that a reader can picture the flow end to end — actor, trigger,
  steps, result.
- Bad: a persona description with no scenario attached.
- Bad example: "A user wants to reset their password."
- Good example: "A user who forgot their password clicks 'Forgot password' on the login page,
  receives an email with a time-limited link, sets a new password, and is redirected to login."

## Requirements

- Good: specific enough for `/task` to build against without asking a follow-up; cites the
  existing pattern it must follow (`file:line`).
- Bad: restates a goal at the same altitude ("the system must let users reset passwords").
- Bad example: "The system must support password reset."
- Good example: "`POST /api/auth/password-reset-request` issues a token stored via the same
  `transaction()` boundary as `app/services/user_service.py`; token expires in 1 hour."

## Success metrics

- Good: a number or an observable state after shipping, not a restated intention.
- Bad: "users are happier" or anything unmeasurable.
- Bad example: "Improves user experience."
- Good example: "Manual password-reset support tickets drop from ~12/week to near zero within
  one release cycle."

## Risks and open questions

- Good: names a real risk or an undecided call, including any point where the idea's stated
  approach contradicts the current architecture (this is mandatory when G1 found one).
- Bad: a vague "there could be risks" with nothing a reviewer can push back on.
- Bad example: "There are some security considerations."
- Good example: "The idea's notes suggest storing the reset token in the `users` row; the
  current schema forbids mutable secrets on `users` (see app/models/user.py) — needs a
  dedicated `password_reset_tokens` table instead."

## Rollout

- Good: sequencing, migration order, flags, and what a rollback looks like.
- Bad: "we will deploy it" with no sequencing.
- Bad example: "Ship in the next release."
- Good example: "Migration lands first and merges to main before the endpoint row is even
  dispatched, so `alembic upgrade head` never has two open heads; endpoint ships behind no
  flag since it is additive."

## Work breakdown

- Good: rows are vertical slices, each independently shippable and reviewable; migrations get
  their own row; a row too large for one PR is split.
- Bad: rows shaped like implementation layers instead of outcomes.
- Bad example: "Add repository method" / "Add router" / "Add frontend form" as three rows.
- Good example: one row "Users can request a password reset email", one row "Users can set a
  new password from a valid reset link", one row "Add password_reset_tokens migration" that
  the first two both depend on.
