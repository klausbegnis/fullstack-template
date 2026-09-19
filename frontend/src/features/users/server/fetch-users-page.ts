import "server-only";
import { apiServerFetch } from "@/lib/api/server-client";
import { toUser } from "@/features/users/api/user-mapper";
import type { PaginatedResponse } from "@/lib/api/envelope";
import type { UserRead } from "@/lib/api/generated/model";
import type { UserFilters } from "@/features/users/model/user-filters";
import type { UsersPage } from "@/features/users/model/user";

/**
 * Fetches one page of users directly from FastAPI, forwarding the incoming
 * request's cookies. Used only from `app/(app)/users/page.tsx` to seed the
 * TanStack Query cache before the client hydrates — the client itself reads
 * this same query key through `userQueries.list`, which fetches through the
 * browser mutator instead.
 */
export async function fetchUsersPageServer(filters: UserFilters): Promise<UsersPage> {
  const response = await apiServerFetch<PaginatedResponse<UserRead>>({
    url: "/users",
    method: "GET",
    params: { page: filters.page, page_size: filters.pageSize },
  });

  return {
    items: response.data.map(toUser),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
    totalPages: response.total_pages,
  };
}
