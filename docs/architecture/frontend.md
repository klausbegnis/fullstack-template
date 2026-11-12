# Frontend architecture

Next.js 16.3.5 (App Router, Turbopack), React 19, TypeScript 5.9 strict, Tailwind CSS 4
(CSS-first — there is no `tailwind.config.*`, tokens live in `globals.css`). RSC by default;
`'use client'` is an opt-in, not a starting point.

## Folder structure

```
src/
  app/            routes only: page/layout/loading/error/not-found. A page imports a
                  container and renders it; it does not itself hold markup or logic.
  features/<f>/   model | api | hooks | containers | components | server | actions | testing
  components/ui/  props-only, feature-agnostic primitives (+ components/layout/)
  lib/            api/{generated,mutator,server-client,envelope,...} | auth/{dal,set-cookie} |
                  query | errors | env
  testing/        renderWithProviders, the MSW server + handlers, factories
tools/eslint/     the local no-comments-except-tsdoc rule
```

`src/lib/api/generated/**` is orval output — regenerated, never hand-edited, and exempt from the
project's lint globs and the boundaries `ui`/`lib` typing (it is ignored in `eslint.config.mjs`).

## The dependency rule

`app -> features -> components(ui) -> lib`, one-way down; `lib` imports only `lib`; **no feature
imports another feature**. Inside a feature the same one-way shape repeats:
`containers -> hooks -> api -> model`, and `model` may import no `react`, `next`, or
`@tanstack/*` — it is plain TypeScript types, zod schemas, and pure functions (see
`features/users/model/user-schema.ts`, `user-filters.ts`).

Enforced by `eslint-plugin-boundaries` in `frontend/eslint.config.mjs`, driven by an
`elements`/`policies` config keyed on `app`/`feature`/`ui`/`lib`/`testing`. The plugin depends on
`settings["import/resolver"]` (`typescript` + `node` resolvers) being configured — without it the
rule silently produces zero violations instead of erroring, so a change to that block should be
verified with a deliberately-broken import. `no-restricted-imports` additionally blocks any
non-server file from importing `**/server/*`, `**/dal`, or `**/server-client` — a client component
reaching into server-only code fails lint, not just at runtime.

There is no separate domain/use-case layer. FastAPI owns the business rules; `features/<f>/model/`
is the intended and sufficient shape for frontend-only logic (form state, filters, view mapping).

## RSC vs. client, and the actual rule

Not "container/presentational" — this repo's own phrasing is **code crosses through imports, data
crosses through props.** A component needs `'use client'` only when it genuinely uses state,
effects, event handlers, or a browser API. `eslint-plugin-use-client`
(`use-client/require-use-client`) checks both directions: a file using a client-only feature
without the directive, and — the more agent-relevant half — a `'use client'` file that uses none,
autofixably removed. **Files under `features/*/components/` are props-only views and carry no
`'use client'`; they still render on the server.** `containers/` is where the client boundary,
hooks, and TanStack Query calls legitimately live.

Route segments load their initial data on the server: `features/users/server/fetch-users-page.ts`
runs in an RSC (`import "server-only"`), calls the API forwarding the incoming request's cookies,
and its result seeds the page. The client-side `useUsers`-style query in `features/users/api/`
then reads through the same TanStack Query key, so the browser mutator only re-fetches on
subsequent interaction, not on first paint.

## The orval-generated client and the anti-corruption layer

`orval.config.ts` reads `../backend/openapi.json` and emits two outputs into
`src/lib/api/generated/`: a `react-query` client (`endpoints/`, one file per OpenAPI tag) and zod
schemas (`zod/`). Every generated call is routed through the single mutator hook,
`src/lib/api/mutator.ts::apiMutator`, which:

- resolves the URL against the `/api/*` Next.js rewrite (the browser never calls FastAPI
  directly);
- sends `credentials: "include"` so the httpOnly session cookies ride along;
- attaches the CSRF header from the readable `app_csrf` cookie on mutating methods;
- unwraps the backend's envelope via `parseApiResponse` and throws a typed `ApiError`
  (`lib/errors/api-error.ts`) on any failure, carrying `status`, `code`, `details`, and
  `request_id` straight from the backend's error contract.

`lib/api/server-client.ts::apiServerFetch` is the equivalent for Server Components, Server
Actions, and Route Handlers — same envelope handling, different cookie-forwarding mechanism (it
reads the incoming request's cookies rather than the browser's).

`lib/api/envelope.ts` types and narrows the three backend envelope shapes
(`SuccessResponse`/`ErrorResponse`/`PaginatedResponse`) and documents the one deliberate
exception: `/auth/login` and `/auth/me` return their resource bare, with no envelope, so
`isSuccessResponse` explicitly excludes anything with `total_pages` before trusting the shape.
On top of that, each feature keeps its own mapper (`features/users/api/user-mapper.ts::toUser`) —
the only place a generated `snake_case` DTO field name is allowed to appear — converting it to a
domain type with idiomatic `camelCase` and parsed `Date`s. A hand-written type that duplicates a
generated request/response DTO shape is a defect: it will silently drift from the backend contract
the next time `generate:api` runs.

## Auth

httpOnly, `SameSite=Lax` cookies: `app_access` (path `/`), `app_refresh` (path `/api/auth`), and a
**readable** `app_csrf` used for double-submit CSRF. Never `localStorage`/`sessionStorage`.
`src/middleware.ts` performs a cheap cookie-presence redirect only and says so in its own comment
— it is a UX optimization, not the authorization boundary (CVE-2025-29927: middleware can be
bypassed). The actual gate is `src/lib/auth/dal.ts`: `import "server-only"` plus React `cache()`
around `getCurrentUser()`, which calls `GET /auth/me` forwarding cookies and treats a 401/403 as
"no session" rather than an error. `requireUser()` wraps it with a redirect (through
`/api/auth/renew` while a session may still be renewable, otherwise to `/login`). Every
protected layout or sensitive Server Action must call one of these, not just rely on middleware
having run.

Sessions renew before `app_access` lapses. `features/auth/containers/session-keeper.tsx`, mounted
by the `(app)` layout with the access token's `exp` (decoded server-side by
`lib/auth/access-expiry.ts`, for scheduling only), calls `refreshSession()`
(`lib/auth/refresh-session.ts`) two minutes before expiry (±15 s; halfway for a short TTL) and again
when the tab returns near expiry. `refreshSession()` is single-flight per tab, serialised across tabs
by the Web Locks API, skips the call when another tab already rotated `app_csrf`, and announces the
result on the `auth` BroadcastChannel. The mutator retries any request once after a 401 (never the
`/auth/refresh|login|logout` calls) with freshly read CSRF. A navigation that arrives without
`app_access` but with `app_csrf` goes through the `/api/auth/renew` Route Handler (middleware, or
`requireUser()` on a 401), which refreshes server-side with this site's origin as `Origin`, forwards
the rotated cookies, sets the 10 s `app_renewed` loop guard and returns to the same path; it only
serves same-origin or address-bar navigations (`Sec-Fetch-Site`). The backend answers a refresh
token rotated less than `AUTH_REFRESH_GRACE_SECONDS` ago, whose successor is unused, with 401
`refresh_superseded` and keeps the session, so two tabs racing past expiry do not trip replay
revocation. The trade-off is deliberate: a stolen refresh token replayed inside that window is
refused but does not revoke the session, and a third rotation that consumes the successor before a
slow sibling arrives turns the sibling's request into a replay that logs the user out. Keep the
grace window short. A session unused for `AUTH_SESSION_IDLE_TTL_SECONDS` (14 days) ends on its own, and an
ended session lands on `/login?next=…&reason=expired`.

Pages ship a nonce-based Content-Security-Policy. The middleware creates a nonce per request
(`lib/security/content-security-policy.ts`) and sets the policy on the response and on the request
headers; the root layout reads the nonce (`lib/security/request-nonce.ts`), which renders every page
per request so Next.js stamps the nonce on its scripts. Production allows scripts only through the
nonce plus `'strict-dynamic'`; `next dev` adds `'unsafe-eval'`. `instrumentation-client.ts` switches
zod to its jitless parsers so it never probes `new Function`.

## Forms

react-hook-form + zod + `zodResolver`, submitted through `useMutation` — never a raw
`<form action>` — for anything that ends at FastAPI. Type the hook as
`useForm<z.input<S>, unknown, z.output<S>>`; the bare `useForm<z.infer<S>>` form mistypes
`handleSubmit` under this repo's strict TypeScript config. Server-side field errors come back
through the backend's `details.errors` and are applied with `lib/errors/field-errors.ts`'s
`applyFieldErrors(error, form.setError)`, including a `root`-level message for a non-field error.
Reference: `features/users/containers/create-user-form.tsx` +
`features/users/components/user-form-view.tsx` (accessible labels wired to `aria-describedby` via
`components/ui/field.tsx`).

React 19 Actions are reserved for the one thing only the Next.js server can do — writing or
clearing the httpOnly session cookie. See `features/auth/actions/login-action.ts` and
`logout-action.ts`; every other mutation goes through TanStack Query so the cache can be
invalidated, which an Action cannot do.

## Testing layers

Vitest runs as two projects (`vitest.config.ts`):

- **`unit`** (`jsdom`, `src/**/*.test.{ts,tsx}`) — component and hook tests via
  `@testing-library/react`, using `testing/render.tsx::renderWithProviders` to wrap a fresh,
  retry-free `QueryClient` per test, and MSW (`testing/msw/server.ts`, started/reset in
  `vitest.setup.ts`) to stub network calls at the fetch layer rather than mocking the generated
  client directly.
- **`node`** (`src/**/*.node.test.ts`) — pure Node-environment tests for server-only modules
  (e.g. `lib/env.node.test.ts`, `lib/api/parse-response.node.test.ts`) that must not run under
  jsdom.

`npm run test` runs both projects with v8 coverage; `npm run test:fast` skips coverage and — via
`scripts/ensure-generated.mjs` — only regenerates the orval client if it is missing, rather than
unconditionally, to keep the fast loop fast.

## Enforcement mechanisms

- `eslint-plugin-boundaries` enforces both the cross-layer rule and the intra-feature rule
  (`containers -> hooks -> api -> model`, `model` free of `react`/`next`/`@tanstack`) and
  `eslint-plugin-use-client` the server/client directive, as part of `npm run lint`, not as advice.
  `no-restricted-syntax` bans `'use client'` outside `containers/`, `process.env` outside
  `lib/env.ts`, `vi.mock` of the generated client and test-id queries; `eslint-plugin-testing-library`
  and `@vitest/eslint-plugin` enforce role-based, behaviour-level tests.
- `src/testing/architecture.node.test.ts` checks the file-level contracts lint cannot see: no
  barrels, a colocated test per container/component/model/mapper/hook, `loading.tsx` + `error.tsx`
  beside async pages, `server-only` in server modules, `requireUser()` in the app layout.
- `.agents/hooks/guard_paths.py` refuses hand edits to `src/lib/api/generated/`;
  `.agents/hooks/post_edit_check.sh` runs prettier and eslint on every edited file.
- `local/no-comments-except-tsdoc` (`tools/eslint/no-comments-except-tsdoc.cjs`) fails lint on any
  comment that is not a `/** */` TSDoc block directly above an exported declaration.
- `no-restricted-imports` blocks client code from importing server-only modules by path pattern.
- `tsc --noEmit` runs in strict mode against the same generated client every build depends on, so
  a backend contract change that breaks a frontend caller fails typecheck, not just at runtime.
- CI (`.github/workflows/ci.yml`) runs typecheck, lint, format check, test, and build on every PR.
