import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getQueryClient } from "@/lib/query/query-client";
import { userQueries } from "@/features/users/api/user-queries";
import { fetchUsersPageServer } from "@/features/users/server/fetch-users-page";
import { DEFAULT_USER_FILTERS } from "@/features/users/model/user-filters";
import { UsersListPage } from "@/features/users/containers/users-list-page";

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
