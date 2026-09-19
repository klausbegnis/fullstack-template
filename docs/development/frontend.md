# Frontend PR checklist

Run everything below from `frontend/`. Needs `backend/openapi.json` to exist (it is committed) —
`generate:api` reads it directly and does not need a running backend.

## Before opening the PR

- [ ] `npm ci` — dependencies installed/up to date.
- [ ] `npm run generate:api` — regenerates the orval client from `backend/openapi.json`. If the
      backend contract changed in this PR, export the new schema first
      (`uv run python -m app.commands.export_openapi` in `backend/`) and commit both
      `backend/openapi.json` and the regenerated `frontend/src/lib/api/generated/**`.
- [ ] `npm run lint` — passes, including `eslint-plugin-boundaries` (import direction),
      `eslint-plugin-use-client` (missing or unnecessary `'use client'`), and the local
      `no-comments-except-tsdoc` rule (no comment anywhere except a TSDoc block above an exported
      declaration).
- [ ] `npm run typecheck` — passes under strict TypeScript.
- [ ] `npm run format` — no diff. `npm run format:write` to fix.
- [ ] `npm run test` — all tests pass (unit + node projects, with coverage).
- [ ] `npm run build` — a clean production build.

## If the change adds a feature or crosses a boundary

- [ ] No feature imports another feature; a shared need goes into `lib/` or `components/ui/`.
- [ ] Inside the feature: `containers -> hooks -> api -> model`, and `model/` has zero
      `react`/`next`/`@tanstack` imports.
- [ ] No new barrel/`index.ts` re-export file outside the orval-generated client.
- [ ] Files under `features/*/components/` carry no `'use client'` — if the linter added it or
      you added it by habit, check whether the file actually needs the client boundary at all
      before keeping it (the file usually belongs in `containers/` instead if it does).

## If the change adds an API call

- [ ] The request/response types come from `lib/api/generated/**` (orval), not a hand-written
      duplicate of a backend DTO.
- [ ] A feature-owned mapper (see `features/users/api/user-mapper.ts`) converts the generated
      `snake_case` shape to the feature's domain type — `snake_case` should not leak past `api/`.
- [ ] Client-side reads go through TanStack Query; an initial page load reads through an RSC
      server-fetch helper in `features/<f>/server/`, not a client-only `useEffect` fetch.
- [ ] Zustand, if used, holds local UI state only — never a copy of server data that TanStack
      Query already owns.

## If the change adds or touches a form

- [ ] zod schema lives in `features/<f>/model/`.
- [ ] `useForm<z.input<S>, unknown, z.output<S>>` with `zodResolver` — not bare `z.infer<S>`.
- [ ] Submission goes through `useMutation`, not a raw `<form action>`, unless this is the
      login/logout Server Action (the one sanctioned use of a React 19 Action here).
- [ ] Every field has an associated label and `aria-describedby` wiring for its error message (see
      `components/ui/field.tsx`).
- [ ] Server-side validation errors are surfaced via `applyFieldErrors` from
      `lib/errors/field-errors.ts`, including a `root`-level message for non-field errors.

## If the change adds a route segment

- [ ] `loading.tsx` and `error.tsx` exist alongside the new `page.tsx` if it does any async data
      fetching.
- [ ] Any protected route/layout calls `requireUser()`/`getCurrentUser()` from
      `lib/auth/dal.ts` — relying on `middleware.ts` alone is a defect (CVE-2025-29927).

## Before pushing

- [ ] Check `git status` for a dirty `src/lib/api/generated/**` or `frontend/AGENTS.md` /
      `frontend/CLAUDE.md` diff caused only by running `npm run dev` — the latter two are
      Next.js-managed and safe to commit as-is, but a stray fully-regenerated client from a stale
      `openapi.json` is not.
- [ ] If `.githooks/pre-commit` is enabled (`git config core.hooksPath .githooks`), it already ran
      prettier, eslint, and `npm run test:fast` on staged files — do not bypass it with
      `--no-verify`.
