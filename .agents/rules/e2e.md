---
paths:
  - "e2e/**"
---

How the Playwright suite in `e2e/` is written and run. It drives the real stack (the Next.js
frontend and its `/api` proxy, the API and Postgres) through a browser, so every rule here exists
to keep it deterministic on a rerun against the same stack and honest about what it covers.

### Locate elements by role, label or visible text in e2e specs

`getByRole`, `getByLabel` and `getByText` are the handles a user has, so a spec breaks when the
page stops being usable and survives a class rename. CSS, XPath, `page.$` and test ids assert
markup instead.

**Incorrect:**

```ts
await page.locator("table tr:first-child a").click();
await page.getByTestId("create-user").click();
```

**Correct:**

```ts
await page.getByLabel("Email").fill(email);
await page.getByRole("button", { name: "Create user" }).click();
```

Enforced by: lint: playwright/no-raw-locators, lint: playwright/no-restricted-locators, lint: no-restricted-syntax

### Wait on web-first assertions, never on time

A fixed sleep is either too short on a cold CI runner or wasted time everywhere else.
`expect(locator).toBeVisible()` and `expect.poll` retry until the condition holds, and every
test ends in an assertion. `test.only` and `test.skip` never reach the branch.

**Incorrect:**

```ts
await page.waitForTimeout(2000);
expect(await page.getByRole("heading").isVisible()).toBe(true);
```

**Correct:**

```ts
await expect(page.getByRole("heading", { level: 1, name: "Users" })).toBeVisible();
```

Enforced by: lint: playwright/no-wait-for-timeout, lint: playwright/prefer-web-first-assertions, lint: playwright/expect-expect, lint: playwright/no-focused-test, lint: playwright/no-skipped-test

### Set worker count and timeouts in playwright.config.ts, never per spec

A spec that times out only on a loaded host is hitting a shared stall, and bumping its own
timeout hides it until the next spec meets it. Fix the cause, then size the suite in
`playwright.config.ts`: workers from `support/workers.ts` (`E2E_WORKERS`, 2 on CI, else the
cores the 1-minute load leaves free over the measured cost of one worker) and the test and
expect budgets from `support/timeouts.ts`. `E2E_RUN_ID` gives a run its own
`test-results/<id>/` and `playwright-report/<id>/`, so a later run never overwrites the traces of
a failed one. A spec-level budget is only for a flow measured to need more than the suite budget
on an idle host, as a named constant with its reason.

**Incorrect:**

```ts
test("admin pages through the users list", async ({ asRole }) => {
  test.setTimeout(60_000);
  await expect(page.getByRole("row")).toHaveCount(21, { timeout: 30_000 });
});
```

**Correct:**

```ts
export default defineConfig({
  workers: chooseWorkers().workers,
  outputDir: runId ? `test-results/${runId}` : "test-results",
  timeout: TEST_TIMEOUT_MS,
  expect: { timeout: EXPECT_TIMEOUT_MS },
});
```

Enforced by: review

### Seed through the API setup project with run-unique data

`specs/seed.setup.ts` signs in as the bootstrapped admin, creates the run's member through the
frontend's `/api` proxy with a run suffix in every email and name, writes `.auth/seed.json` and
stores one session per role under `e2e/.auth/`. Specs read ids from the `seed` fixture and open
sessions with `asRole(role)`; they never hard-code an id, rely on list ordering, or renew or
revoke a stored session another test shares (sign the user in on a context of its own instead).
An API mutation from a spec goes through `mutationHeaders` in `flows/seed-api.ts`: the API
refuses a cookie-authenticated mutation without an allowed `Origin`, and the session endpoints
check the double-submit `X-CSRF-Token` against the `app_csrf` cookie.

**Incorrect:**

```ts
await page.goto("/users/0a3460e8-80c1-45d4-b0bd-85b52653e76e");
```

**Correct:**

```ts
const { page } = await asRole("admin");
await page.goto(`/users/${seed.users.member.id}`);
```

Enforced by: review

### Run a test on the phone project only when the viewport is what it proves

`desktop-chromium` runs every test except those tagged `@phone-only`. `phone-chromium` runs only
the tests tagged `@phone` or `@phone-only` (its `grep: /@phone(-only)?\b/`): tag a test `@phone`
when it also proves something at 390 px, and `@phone-only` when only a phone shows it (the tab
bar, the header menu). A test never forces a 390 px viewport itself; it takes the phone
project's. The route smoke tags its non-redirect entries `@phone`; redirects and a member's view
of an admin page run on desktop only. Business rules, permissions and API contracts do not
change with the viewport: prove them once, and prove an API-only contract in the backend tests.

**Incorrect:**

```ts
test("the tab bar marks the current destination", async ({ asRole }) => {
  const { page } = await asRole("admin");
  await page.setViewportSize({ width: 390, height: 844 });
});
```

**Correct:**

```ts
test("the tab bar marks the current destination", { tag: "@phone-only" }, async ({ asRole }) => {
  const { page } = await asRole("admin");
});
```

Enforced by: e2e/playwright.config.ts (phone-chromium `grep`, desktop-chromium `grepInvert`), review

### Register every route in the route manifest

`e2e/routes/route-manifest.ts` is the one list the smoke spec visits: each entry names its h1,
its audience and, for an admin route, what a member gets there. `specs/route-coverage.spec.ts`
fails when a `frontend/src/app/**/page.tsx` route or a `navItems` link has no manifest entry,
when a redirect target is not itself an entry, when an admin entry has no `memberOutcome`, or
when an allowlist entry is stale or has an empty reason. A new page ships with its manifest
entry or with an allowlist reason a reviewer accepted.

Enforced by: e2e/specs/route-coverage.spec.ts

### Keep the page guards on and justify every exclusion in `known-findings.ts`

The `pageGuards` fixture fails a test on any console error, uncaught page error or 5xx response;
the smoke run also fails on horizontal overflow and on serious or critical axe violations. An app
defect is fixed in the frontend; only one that is truly out of scope is recorded in
`e2e/support/known-findings.ts` as the narrowest exclusion (one axe rule on one route, one
message on one route) with its reason. A per-test `pageGuards.allow(kind, pattern, reason)` is
only for an error that is the expected behaviour, such as the 403 a member's page logs when the
API refuses it admin-only data.

**Incorrect:**

```ts
page.removeAllListeners("console");
```

**Correct:**

```ts
pageGuards.allow("console-error", /status of 403/, "The API refuses admin-only data to a member.");
```

Enforced by: review

### Run the suite through the compose `e2e` service against a stack with the admin bootstrapped

The suite starts no server. The `e2e` service (profile `e2e`, image
`mcr.microsoft.com/playwright` pinned by digest to the `@playwright/test` version) runs the
browser on the compose network, reaching `http://frontend:3000`, so a host browser never shares
the host's network namespace with other stacks. It bind-mounts the repo (the route guard reads
`frontend/src`) and runs as `E2E_UID:E2E_GID` so `e2e/playwright-report` and `e2e/test-results`
stay owned by you. Bring the stack up with `ENVIRONMENT=development`, `AUTH_COOKIE_SECURE=false`
(the browser reaches the frontend over plain http) and raised `RATE_LIMIT_LOGIN_PER_IP` and
`RATE_LIMIT_LOGIN_PER_EMAIL`, because the whole suite signs in from one container IP and the
seed signs the admin in once per run; then create the admin the seed signs in with, run
`npm ci` in `e2e/` and start the service.

**Incorrect:**

```sh
cd e2e && npx playwright install chromium && npx playwright test
```

**Correct:**

```sh
ENVIRONMENT=development AUTH_COOKIE_SECURE=false \
  RATE_LIMIT_LOGIN_PER_IP=10000 RATE_LIMIT_LOGIN_PER_EMAIL=10000 \
  docker compose up --build --wait
docker compose exec -T api python -m app.commands.bootstrap_admin e2e-admin@example.test --password e2e-not-a-real-pw --yes
npm ci --prefix e2e
E2E_UID="$(id -u)" E2E_GID="$(id -g)" docker compose --profile e2e run --rm e2e
```

Enforced by: .github/workflows/ci.yml (E2E job)
