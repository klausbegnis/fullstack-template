import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getQueryClient } from "@/lib/query/query-client";
import { userQueries } from "@/features/users/api/user-queries";
import { fetchUserDetailServer } from "@/features/users/server/fetch-user-detail";
import { UserDetailPage } from "@/features/users/containers/user-detail-page";

export interface PageProps {
  params: Promise<{ userId: string }>;
}

export default async function Page({ params }: PageProps) {
  const { userId } = await params;
  const queryClient = getQueryClient();
  const detailOptions = userQueries.detail(userId);

  await queryClient
    .query({
      queryKey: detailOptions.queryKey,
      queryFn: () => fetchUserDetailServer(userId),
      staleTime: detailOptions.staleTime,
    })
    .catch(() => undefined);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UserDetailPage userId={userId} />
    </HydrationBoundary>
  );
}
