---
paths:
  - "frontend/src/**/*.test.{ts,tsx}"
  - "frontend/src/**/*.node.test.ts"
  - "frontend/src/testing/**"
  - "frontend/vitest.*"
---

What a test looks like per layer, where it lives, and which seams it is allowed to use. The
code under test is governed by `frontend/architecture.md`, `frontend/server-client.md`,
`frontend/data-and-forms.md` and `frontend/ui-components.md`.

### Match the test type to the layer

`model` is a pure unit test; an `api` mapper is a unit test on the DTO shape; `hooks` use
`renderHook`; `components` render with plain props and query by role; `containers` use
`renderWithProviders` with MSW and cover one happy and one error path; `server/` helpers and
`lib/` server code run as `.node.test.ts` because they import `server-only`.

Enforced by: frontend/src/testing/architecture.node.test.ts

### Colocate every test beside the file it covers

`user-mapper.test.ts` sits next to `user-mapper.ts`. A `__tests__/` directory hides which
modules have no test and breaks the mechanical pairing the architecture test relies on.

Enforced by: frontend/src/testing/architecture.node.test.ts

### Intercept the network with MSW only

MSW exercises the real generated client, the real mutator and the real envelope parsing, so a
backend contract change breaks the test. `vi.mock` of `@/lib/api/generated/*` or of `fetch`
replaces exactly the code most likely to be wrong with a hand-written stub that agrees with
itself forever.

**Incorrect:**

```ts
vi.mock("@/lib/api/generated/endpoints/users/users", () => ({
  listUsers: vi.fn().mockResolvedValue({ data: [] }),
}));
```

**Correct:**

```ts
server.use(
  http.get("*/users", () =>
    HttpResponse.json({ success: true, data: [buildUserDto()], total: 1, page: 1, page_size: 20, total_pages: 1 }),
  ),
);
```

Enforced by: lint: no-restricted-syntax

### Query by role, label or text

Those are the handles a user actually has, so a test written with them fails when the component
becomes unusable and survives a refactor that does not change behaviour. A `data-testid`, a
`container.querySelector` or a raw node access asserts the implementation instead. Use
`userEvent`, not `fireEvent` — it dispatches the full event sequence a real interaction does.

Enforced by: lint: testing-library/no-container, lint: testing-library/no-node-access, lint: testing-library/prefer-user-event

### Keep factories in `features/<f>/testing/factories.ts`

A factory builds both the domain object and the backend DTO shape MSW must return, so the two
stay in step. It lives inside the feature: a shared `src/testing/` module that imports every
feature is the same coupling as a feature importing another feature.

Enforced by: review

### Assert instead of snapshotting, and never commit `.only`

A snapshot records whatever the code did, including the bug, and is updated reflexively when it
fails. A committed `.only` silently drops the rest of the file from the run, and a `.skip`
leaves a test nobody notices is dead. Every test ends in an assertion.

Enforced by: lint: vitest/no-focused-tests, lint: vitest/no-disabled-tests, lint: vitest/expect-expect

### Keep `onUnhandledRequest: "error"` and a fresh `QueryClient` per test

An unhandled request that falls through to the network makes a test pass for a reason the test
does not describe. A `QueryClient` shared between tests carries the previous test's cache and
its retry timers into the next one; `renderWithProviders` builds a retry-free client each time.

Enforced by: review
