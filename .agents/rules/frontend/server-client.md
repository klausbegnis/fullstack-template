---
paths:
  - "frontend/src/app/**"
  - "frontend/src/features/*/server/**"
  - "frontend/src/features/*/actions/**"
  - "frontend/src/lib/auth/**"
  - "frontend/src/middleware.ts"
---

Where the server/client boundary falls, how a route segment loads its data, and where
authorization is actually decided. Import direction is in `frontend/architecture.md`; client
data and forms are in `frontend/data-and-forms.md`.

### Render on the server by default and confine `'use client'` to containers

Code crosses through imports, data crosses through props — so a directive is needed only where
state, effects or browser APIs are genuinely used. A props-only view may render an event callback
received from its container without owning the client boundary. Inside a feature that is
`containers/**` only: the directive is banned by lint in `components`, `model`, `api`, `hooks`,
`server` and `testing`. Hooks in `api/` and `hooks/` use client features without the directive
because they are only ever imported from a container, which is the boundary. Outside features it
is legal in `components/**`, `app/**` boundary files and `lib/query`. A `'use client'` on a view
or a mapper drags its whole import subtree into the browser bundle. `eslint-plugin-use-client`
fails on a missing or unnecessary directive everywhere except `features/*/{api,hooks}`.

Enforced by: lint: no-restricted-syntax, lint: use-client/require-use-client

### Keep a page to prefetch, `HydrationBoundary` and one container

A `page.tsx` seeds the query cache and renders one container; it holds no markup and no logic,
so the same screen can be reached from a different route without copying anything. It may
import only a feature's `containers`, `server`, `api` or `model`, plus `components/ui` and
`lib`.

**Correct:**

```tsx
export default async function Page() {
  const queryClient = getQueryClient();
  const listOptions = userQueries.list(DEFAULT_USER_FILTERS);

  await queryClient
    .query({
      queryKey: listOptions.queryKey,
      queryFn: () => fetchUsersPageServer(DEFAULT_USER_FILTERS),
      staleTime: listOptions.staleTime,
    })
    .catch(() => undefined);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UsersListPage />
    </HydrationBoundary>
  );
}
```

Enforced by: lint: boundaries/dependencies, review

### Give every async `page.tsx` a sibling `loading.tsx` and `error.tsx`

Without them an awaited page blocks the whole route on its slowest fetch and a thrown error
climbs to the root boundary, losing the layout and the navigation with it.

Enforced by: frontend/src/testing/architecture.node.test.ts

### Load initial data in `features/<f>/server/*.ts` behind `server-only`

A server fetch helper starts with `import "server-only"`, goes through `apiServerFetch` so the
incoming request's cookies are forwarded to FastAPI, and seeds the same query key the container
reads through `<x>Queries`. A different key means the client refetches immediately and the
prefetch was wasted.

Enforced by: frontend/src/testing/architecture.node.test.ts, lint: no-restricted-imports

### Gate authorization in `lib/auth/dal.ts`, never in middleware

`middleware.ts` does a cookie-presence redirect only. Middleware can be bypassed
(CVE-2025-29927), so it is a UX optimization and never the boundary. Next 16.3+ renames the
file convention to `proxy.ts`; the name changes, the security point does not. The real gate is
`requireUser()`/`getCurrentUser()` from `lib/auth/dal.ts` — `import "server-only"`, wrapped in
React `cache()` so one render verifies the session once — and every protected layout, route and
Server Action calls it.

**Incorrect:**

```tsx
// DO NOT DO THIS: middleware.ts already redirected, so this page trusts it
export default async function Page() {
  return <AdminPanel />;
}
```

**Correct:**

```tsx
export default async function AppLayout({ children }: AppLayoutProps) {
  const user = await requireUser();
  return <AppShell actions={<LogoutButton />}>{children}</AppShell>;
}
```

Enforced by: frontend/src/testing/architecture.node.test.ts, review

### Reserve Server Actions for the session cookie

`loginAction` and `logoutAction` exist because writing an httpOnly cookie is the one thing only
the Next server can do. Every other mutation goes through TanStack Query, which gives it
pending state, error handling and cache invalidation for free. An action authorizes inside its
own body — it is a public POST endpoint, and the middleware redirect does not cover it.

Enforced by: lint: boundaries/dependencies, review

### Keep no mutable state at module scope in server code

Module scope is process-wide and shared by every concurrent request, so a cached user or a
mutable counter there leaks one visitor's data into another's response. Request-scoped state
belongs in `cache()` or in the arguments.

Enforced by: review

### Await independent work concurrently and stream slow data

Two sequential `await`s that do not depend on each other double the page's time to first byte;
`Promise.all` does not. Data that stays slow belongs behind its own `<Suspense>` boundary so
the shell renders while it resolves.

Enforced by: review

### Call `cookies()` and `headers()` only in leaf server helpers

Reading either in a page or layout body opts that whole segment into dynamic rendering, so a
mostly-static route loses prerendering for one header lookup. `apiServerFetch` already reads
them at the leaf.

Enforced by: review

### Push non-blocking side effects into `after()`

Logging, analytics and cache invalidation do not need to finish before the response is sent.
Awaiting them inline adds their latency to every request.

Enforced by: review

### Send fields, not entities, across the RSC boundary

Everything passed to a client component is serialized into the HTML payload, so passing a whole
entity ships fields the view never renders — including ones that should not leave the server.
`Date`s do not survive the crossing; the mapper reconstructs them on the client.

Enforced by: review
