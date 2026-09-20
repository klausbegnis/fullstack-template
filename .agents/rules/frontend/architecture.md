---
paths:
  - "frontend/src/**"
---

The import graph of the Next.js application: which direction dependencies run, where generated
code and environment access are allowed, and the file-level conventions that hold everywhere
under `src/`. Server/client placement is in `frontend/server-client.md`, data access in
`frontend/data-and-forms.md`, views in `frontend/ui-components.md`.

### Import downward only: app, features, components, lib

`app/` may import features, `components/ui` and `lib`; a feature may import `components` and
`lib`; `lib` imports only `lib`. No feature imports another feature — that is the edge that
turns two deletable slices into one tangle, and the only way to share is to move the shared
part down into `components` or `lib`.

Enforced by: lint: boundaries/dependencies

### Respect the layer order inside a feature

`containers -> hooks | api | model | components`, `hooks -> api | model`, `api -> model`,
`components -> model | ui | lib`, `server -> api | model | lib`, `actions -> model | lib`.
`model/` is plain types, zod schemas and pure functions: it imports no `react`, no `next*` and
no `@tanstack/*`, which is what keeps it testable in a bare node environment and importable
from server code.

**Incorrect:**

```ts
// src/features/users/model/user.ts
import { useQuery } from "@tanstack/react-query";
import { useUsersFilters } from "@/features/users/hooks/use-users-filters";
```

**Correct:**

```ts
// src/features/users/model/user.ts
export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "member";
  disabledAt: Date | null;
}
```

Enforced by: lint: boundaries/dependencies, lint: boundaries/external

### Never write a barrel `index.ts`

A re-export file makes every importer depend on every module the barrel names, which defeats
tree-shaking, produces import cycles that only appear at runtime, and hides the boundary
violations the layer rules are meant to catch. Import the module directly. The generated client
is the single exception, because orval writes it.

Enforced by: frontend/src/testing/architecture.node.test.ts

### Treat `src/lib/api/generated/**` as build output

Orval regenerates it from `backend/openapi.json` on every `typecheck`, `test` and `build`, so
an edit there is gone on the next run and is not committed. Request and response types come
from that output; a hand-written DTO interface is a second source of truth that drifts the
moment the backend schema changes.

Enforced by: hook: .agents/hooks/guard_paths.py, review

### Confine `snake_case` to the feature's mapper

FastAPI speaks `snake_case`, the app speaks `camelCase`. `features/<f>/api/<x>-mapper.ts` is
the one place the two meet, so a field rename in the backend produces one type error in one
file instead of a scatter of silent `undefined`s.

Enforced by: review

### Never import a server-only module from client code

`lib/auth/dal.ts`, `lib/api/server-client.ts` and every `features/*/server/*.ts` carry
`import "server-only"`. Importing one from a client component turns a build-time error into a
bundling attempt that can leak a server secret into the browser bundle.

Enforced by: lint: no-restricted-imports

### Read environment variables only in `lib/env.ts`

One module validates and narrows `process.env`, splitting the server-only values from the
`NEXT_PUBLIC_` ones. A `process.env.X` elsewhere is unvalidated, is `undefined` in the browser
whenever the prefix is missing, and makes the set of required variables impossible to enumerate.

Enforced by: lint: no-restricted-syntax

### Configure Tailwind 4 in CSS and never inline a style object

Tokens live in `@theme` inside `src/app/globals.css`; there is no `tailwind.config.*` in
Tailwind 4 and adding one splits the source of truth. A `style={{ ... }}` object bypasses the
token scale and the dark-mode variants along with it.

Enforced by: lint: react/forbid-dom-props, review

### Name files in kebab-case and export one component per file

`user-detail-view.tsx` exports `UserDetailView`. A predictable mapping is what lets the
architecture tests pair a component with its colocated test and a scaffold place a file without
asking.

Enforced by: review

### Write TSDoc above exports and no other comments

`local/no-comments-except-tsdoc` allows a `/** */` block directly above an exported
declaration and nothing else — no `//`, no inline `/* */`. A comment inside a function is a
name that has not been chosen yet.

Enforced by: lint: local/no-comments-except-tsdoc
