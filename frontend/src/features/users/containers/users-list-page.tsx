"use client";

import { useQuery } from "@tanstack/react-query";
import { usePagerControl } from "@/components/ui/use-pagination";
import { userQueries } from "@/features/users/api/user-queries";
import { useUsersFilters } from "@/features/users/hooks/use-users-filters";
import { USERS_HEADING_ID, UsersListView } from "@/features/users/components/users-list-view";

/**
 * Wires the users list query and its pagination state to the presentational
 * view. Prefetched server-side by `app/(app)/users/page.tsx`, then read here
 * through `useQuery` for client-driven pagination; the previous page stays on
 * screen while the next one loads, and `usePagerControl` keeps the heading in
 * view and focus inside the pager.
 */
export function UsersListPage() {
  const { filters, goToPage } = useUsersFilters();
  const { data, isPending, isError } = useQuery(userQueries.list(filters));
  const control = usePagerControl(goToPage, USERS_HEADING_ID);

  return (
    <UsersListView
      users={data?.items ?? []}
      status={isError ? "error" : isPending ? "loading" : "ready"}
      pager={{
        page: filters.page,
        pageCount: Math.max(1, data?.totalPages ?? 1),
        totalItems: data?.total ?? 0,
        pageSize: filters.pageSize,
        ...control,
      }}
    />
  );
}
