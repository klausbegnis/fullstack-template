---
paths:
  - "frontend/src/features/*/api/**"
  - "frontend/src/features/*/containers/**"
  - "frontend/src/features/*/hooks/**"
  - "frontend/src/features/*/model/**"
---

How a feature reads and writes server data on the client: query keys, mutations, the DTO
boundary, and the form recipe. Where the client boundary falls is in
`frontend/server-client.md`; import direction is in `frontend/architecture.md`.

### Build every query key in the feature's `<x>Queries` factory

One object in `api/` owns the key hierarchy and the `queryOptions` for every query, so a
mutation can invalidate a whole branch by name and a server prefetch can seed exactly the key
the container will read. A key spelled inline somewhere else is a cache entry nothing
invalidates.

**Correct:**

```ts
export const userQueries = {
  all: () => ["users"] as const,
  lists: () => [...userQueries.all(), "list"] as const,
  list: (filters: UserFilters) =>
    queryOptions({
      queryKey: [...userQueries.lists(), filters],
      queryFn: () => fetchUsersPage(filters),
      staleTime: 60_000,
    }),
};
```

Enforced by: lint: boundaries/dependencies, review

### Write mutations as `use-<verb>-<x>.ts` hooks that invalidate on success

A mutation hook lives in `api/`, calls the generated client, maps the DTO, and invalidates the
feature's keys in `onSuccess`. Optimistic updates are allowed only with a rollback in
`onError`. Authorization is never assumed from the UI or from `src/middleware.ts` (`proxy.ts`
in Next 16.3+ — same file, same security point: a redirect, not a gate); the backend route's
auth dependency is the check.

**Correct:**

```ts
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation<User, unknown, CreateUserValues>({
    mutationFn: async (values) => toUser(unwrapGenerated<UserRead>(await createUser(values))),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userQueries.lists() });
    },
  });
}
```

Enforced by: review

### Convert DTOs to domain objects only in `api/<x>-mapper.ts`

`toUser` unwraps the envelope, camelCases the fields and parses the date strings into `Date`s.
Keeping it in one tested function is what lets every container, view and test share one shape
of the entity, and it has a colocated test.

Enforced by: frontend/src/testing/architecture.node.test.ts

### Keep Zustand for UI state only

A copy of server data in a store is a second cache with no invalidation, no staleness and no
refetch — and it diverges from TanStack Query's copy on the first mutation. Stores hold things
the server does not own: a sidebar toggle, a selected tab.

Enforced by: review

### Derive state during render instead of syncing it in an effect

A `useState` mirroring a prop plus a `useEffect` writing it back renders twice and shows the
stale value in between. Compute the value in the render body; fetch through TanStack Query, not
in an effect.

**Incorrect:**

```tsx
const [fullName, setFullName] = useState("");
useEffect(() => {
  setFullName(`${user.firstName} ${user.lastName}`);
}, [user]);
```

**Correct:**

```tsx
const fullName = `${user.firstName} ${user.lastName}`;
```

Enforced by: review

### Define components at module scope and render conditionals with a ternary

A component defined inside another is a new type on every render, so React unmounts and
remounts its whole subtree and loses the state in it. And `{count && <Badge />}` renders a
literal `0` when `count` is `0` — a ternary returning `null` does not. Pending UI comes from
`useTransition` so the interaction stays responsive.

Enforced by: lint: react/no-unstable-nested-components, lint: react/jsx-no-leaked-render

### Type forms with `z.input` and `z.output` and submit through `useMutation`

The zod schema lives in `model/`. Under strict TypeScript, `useForm<z.infer<S>>` mistypes
`handleSubmit` whenever the schema has a default or a transform, because the value before and
after parsing differ; the three-parameter form states both. Submit through the mutation hook,
map server field errors with `applyFieldErrors`, and disable the submit button while pending.

**Incorrect:**

```tsx
const form = useForm<z.infer<typeof createUserSchema>>({
  resolver: zodResolver(createUserSchema),
});
```

**Correct:**

```tsx
const form = useForm<CreateUserInput, unknown, CreateUserValues>({
  resolver: zodResolver(createUserSchema),
  defaultValues: { name: "", email: "", password: "", role: "member" },
});

const submit = form.handleSubmit(async (values) => {
  try {
    const user = await mutation.mutateAsync(values);
    router.push(`/users/${user.id}`);
  } catch (error) {
    form.setError("root", { type: "server", message: applyFieldErrors(error, form.setError) });
  }
});
```

Enforced by: mypy, review

### Import `next/dynamic` only inside a container

A dynamic import is a client-side code-splitting decision, and `{ ssr: false }` is only legal
in a file that already carries `'use client'`. In a server component it either throws at build
time or silently disables prerendering for the segment.

Enforced by: review

### Keep `hooks/` free of network calls

`hooks/` holds UI-state hooks — filters, pagination, selection — and imports only `api` types
and `model`. A hook that fetches is a query in the wrong layer: it cannot be prefetched on the
server and it is not reachable from `<x>Queries`. Test them with `renderHook`.

Enforced by: frontend/src/testing/architecture.node.test.ts
