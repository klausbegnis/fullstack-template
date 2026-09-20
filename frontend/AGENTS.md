# frontend — Next.js app

Next.js 16 (App Router, Turbopack) + React 19 + TypeScript strict + Tailwind 4, laid out
`src/app/` (route groups `(app)` and `(auth)`), `src/features/<f>/{model,api,hooks,containers,components,server,actions}`,
`src/components/{ui,layout}`, `src/lib/{api,auth,errors,query}` and `src/testing/`. The API client
under `src/lib/api/generated/` is orval output regenerated from `backend/openapi.json`. The
repo-wide guide is the root [`AGENTS.md`](../AGENTS.md); the reasoning is in
[`docs/architecture/frontend.md`](../docs/architecture/frontend.md).

## Read before editing

| Rule file                                                                                 | Applies to                                                                                                                                                 |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`.agents/rules/frontend/architecture.md`](../.agents/rules/frontend/architecture.md)     | `frontend/src/**`                                                                                                                                          |
| [`.agents/rules/frontend/server-client.md`](../.agents/rules/frontend/server-client.md)   | `frontend/src/app/**`, `frontend/src/features/*/server/**`, `frontend/src/features/*/actions/**`, `frontend/src/lib/auth/**`, `frontend/src/middleware.ts` |
| [`.agents/rules/frontend/data-and-forms.md`](../.agents/rules/frontend/data-and-forms.md) | `frontend/src/features/*/{api,containers,hooks,model}/**`                                                                                                  |
| [`.agents/rules/frontend/ui-components.md`](../.agents/rules/frontend/ui-components.md)   | `frontend/src/components/**`, `frontend/src/features/*/components/**`                                                                                      |
| [`.agents/rules/frontend/testing.md`](../.agents/rules/frontend/testing.md)               | `frontend/src/**/*.test.{ts,tsx}`, `frontend/src/**/*.node.test.ts`, `frontend/src/testing/**`, `frontend/vitest.*`                                        |

## Checks

Run from `frontend/`. `typecheck`, `test` and `build` regenerate the API client first;
`lint` does not.

| Task              | Command                                                           |
| ----------------- | ----------------------------------------------------------------- |
| Lint / format     | `npm run lint` · `npm run format` (`npm run format:write` to fix) |
| Typecheck         | `npm run typecheck`                                               |
| Test              | `npm run test` (coverage) · `npm run test:fast`                   |
| Build             | `npm run build`                                                   |
| Regenerate client | `npm run generate:api`                                            |

## Code Review Rules

### Boundaries

- A feature must not import another feature. Safe path: move the shared part down into `src/components/ui` or `src/lib`.
- A file under `features/*/model/` must not import `react`, `next` or `@tanstack/*`. Safe path: keep it types, zod schemas and pure functions.
- Do not add an `index.ts` barrel. Safe path: import the module by its own path.

### Server and client

- Do not add `'use client'` outside `features/*/containers/` and `components/layout/`. Safe path: pass data and callbacks as props into a server-rendered view.
- Do not treat `src/middleware.ts` (`proxy.ts` in Next 16.3+) as the authorization gate — it can be bypassed. Safe path: `requireUser()` from `src/lib/auth/dal.ts` in the protected layout, route and Server Action.
- Do not use a Server Action for a mutation other than setting or clearing the session cookie. Safe path: a `useMutation` hook in the feature's `api/`.
- Do not ship an async `page.tsx` without a sibling `loading.tsx` and `error.tsx`. Safe path: add both beside the page.

### Data

- Do not edit or commit `src/lib/api/generated/`. Safe path: change the backend schema, re-export `openapi.json`, run `npm run generate:api`.
- Do not spell a query key inline or hand-write a DTO type. Safe path: the feature's `<x>Queries` factory and the generated `UserRead`-style types through `api/<x>-mapper.ts`.

### Forms

- Do not type a form as `useForm<z.infer<S>>`. Safe path: `useForm<z.input<S>, unknown, z.output<S>>` with `zodResolver`.

### Tests

- Do not `vi.mock` the generated client or `fetch`, and do not query by test id. Safe path: an MSW handler plus role, label or text queries.
