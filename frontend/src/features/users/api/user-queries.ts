import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import {
  listUsersUsersGet,
  getUserUsersUserIdGet,
} from "@/lib/api/generated/endpoints/users/users";
import { unwrapGenerated } from "@/lib/api/unwrap-generated";
import { toUser } from "@/features/users/api/user-mapper";
import type { UserRead } from "@/lib/api/generated/model";
import type { UserFilters } from "@/features/users/model/user-filters";
import type { UsersPage } from "@/features/users/model/user";

async function fetchUsersPage(filters: UserFilters): Promise<UsersPage> {
  const response = await listUsersUsersGet({ page: filters.page, page_size: filters.pageSize });
  return {
    items: response.data.map(toUser),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
    totalPages: response.total_pages,
  };
}

async function fetchUserDetail(userId: string) {
  const dto = unwrapGenerated<UserRead>(await getUserUsersUserIdGet(userId));
  return toUser(dto);
}

export const userQueries = {
  all: () => ["users"] as const,
  lists: () => [...userQueries.all(), "list"] as const,
  list: (filters: UserFilters) =>
    queryOptions({
      queryKey: [...userQueries.lists(), filters],
      queryFn: () => fetchUsersPage(filters),
      staleTime: 60_000,
      placeholderData: keepPreviousData,
    }),
  details: () => [...userQueries.all(), "detail"] as const,
  detail: (userId: string) =>
    queryOptions({
      queryKey: [...userQueries.details(), userId],
      queryFn: () => fetchUserDetail(userId),
      staleTime: 60_000,
    }),
};
