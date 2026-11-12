---
paths:
  - "frontend/src/components/**"
  - "frontend/src/features/*/components/**"
---

Rules for view components: the shared primitives under `components/ui`, the layout shell under
`components/layout`, and the feature-owned views under `features/*/components/`. Where state
and data live is in `frontend/data-and-forms.md`; the client boundary is in
`frontend/server-client.md`.

### Keep component files props-only

A view takes data and callbacks as props and renders them. It carries no `'use client'` and
stays server compatible — "presentational" is not a reason to go client-side. No data
hooks, no `@tanstack/*`, no `next/navigation`: behaviour arrives from the container that owns
it, which is also what makes the view testable by rendering it with plain props.

**Incorrect:**

```tsx
"use client";
export function UsersListView({ page }: { page: number }) {
  const { data } = useQuery(userQueries.list({ page, pageSize: 20 }));
  const router = useRouter();
  return <table>{/* ... */}</table>;
}
```

**Correct:**

```tsx
export interface UsersListViewProps {
  users: readonly User[];
  status: "loading" | "error" | "ready";
  canGoToNextPage: boolean;
  onNextPage: () => void;
}

export function UsersListView({ users, status, canGoToNextPage, onNextPage }: UsersListViewProps) {
  return <div className="flex flex-col gap-4">{/* ... */}</div>;
}
```

A feature view may hand a callback prop to an element (`onClick={onNextPage}`, or an arrow that
only calls callback props); any other handler body is event behaviour and belongs to the
container.

Enforced by: lint: local/no-imperative-event-handlers, lint: no-restricted-syntax, lint: boundaries/external

### Every overlay closes on outside click and Escape and returns focus

A popup the user cannot dismiss by clicking away is a trap, and every hand-rolled copy of the
open/close logic drifts. A modal is a native `<dialog>` rendered through `Dialog` and opened only
by `useModalDialog` from `components/ui/use-modal-dialog.ts`: Escape, the native cancel and a
pointer on the backdrop call `onClose`, `initialFocus` places focus on open, and focus returns to
the trigger on close. A non-modal panel, popover or dropdown takes its ref from
`useDismissiblePanel` (Escape and a pointer outside the panel and its trigger dismiss it). A
feature that needs more (per-step focus) wraps the primitive instead of calling `showModal()`
itself. A full-screen dialog has no backdrop to click and keeps Escape plus a visible close
button. Clicking outside an editor with unsaved changes is the same as its close button; a close
the container refuses while a save is pending stays refused, because the guard lives in `onClose`.

**Incorrect:**

```tsx
useEffect(() => {
  if (open) dialogRef.current?.showModal();
}, [open]);
```

**Correct:**

```tsx
const dialogRef = useModalDialog(open, close, { initialFocus: "button, a[href]" });
return <Dialog dialogRef={dialogRef} title="Edit item" onClose={close}>{/* ... */}</Dialog>;
```

Enforced by: lint: no-restricted-properties (showModal outside components/ui), frontend/src/components/ui/use-modal-dialog.test.tsx, frontend/src/components/ui/use-dismissible-panel.test.tsx

### Express async state as a discriminated `status` prop

`"loading" | "error" | "ready"` makes the three states exhaustive and reviewable in one place,
where separate `isLoading`/`isError` booleans allow four combinations of which two are
nonsense. Render loading as `role="status"` and failure as `role="alert"` so the change is
announced.

Enforced by: review

### Render every input through `components/ui/field.tsx`

`Field` pairs a visible `<label htmlFor>` with the control and wires the error text through
`aria-describedby`, so a screen reader hears the message the sighted user sees. Placeholder
text is not a label. Every button has an accessible name — an icon-only button needs one
explicitly.

Enforced by: lint: testing-library/prefer-screen-queries, review

### Compose components instead of adding boolean props

A third boolean multiplies the states the component must handle and the tests it needs.
Children and compound sub-components let the caller assemble the variant it wants without the
component enumerating them.

Enforced by: review

### Keep `components/ui` feature-agnostic

A primitive that imports a domain type stops being reusable and creates the `ui -> features`
edge the boundary config forbids. Anything that knows what a `User` is belongs in
`features/<f>/components/`.

Enforced by: lint: boundaries/dependencies

### Take colors and spacing from the `globals.css` tokens

Classes are merged with `cn()` so a caller's override wins predictably. A raw hex value or an
inline style object bypasses the `@theme` scale, and with it the dark-mode variants and every
future token change.

Enforced by: lint: react/forbid-dom-props
