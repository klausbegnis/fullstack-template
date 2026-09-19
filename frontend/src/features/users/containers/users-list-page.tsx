"use client";

import { useQuery } from "@tanstack/react-query";
import { userQueries } from "@/features/users/api/user-queries";
import { useUsersFilters } from "@/features/users/hooks/use-users-filters";
import { UsersListView } from "@/features/users/components/users-list-view";

/**
 * Wires the users list query and its pagination state to the presentational
 * view. Prefetched server-side by `app/(app)/users/page.tsx`, then read here
 * through `useQuery` for client-driven pagination.
 */
export function UsersListPage() {
  const { filters, goToPage, canGoToPreviousPage, canGoToNextPage } = useUsersFilters();
  const { data, isPending, isError } = useQuery(userQueries.list(filters));

  return (
    <UsersListView
      users={data?.items ?? []}
      status={isError ? "error" : isPending ? "loading" : "ready"}
      page={filters.page}
      totalPages={data?.totalPages ?? 1}
      canGoToPreviousPage={canGoToPreviousPage}
      canGoToNextPage={canGoToNextPage(data?.totalPages ?? 1)}
      onPreviousPage={() => goToPage(filters.page - 1)}
      onNextPage={() => goToPage(filters.page + 1)}
    />
  );
}
