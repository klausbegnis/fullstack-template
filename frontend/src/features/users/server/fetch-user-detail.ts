import "server-only";
import { apiServerFetch } from "@/lib/api/server-client";
import { toUser } from "@/features/users/api/user-mapper";
import type { UserRead } from "@/lib/api/generated/model";
import type { User } from "@/features/users/model/user";

/**
 * Fetches a single user directly from FastAPI, forwarding the incoming
 * request's cookies. Used only from `app/(app)/users/[userId]/page.tsx` to
 * seed the TanStack Query cache before the client hydrates.
 */
export async function fetchUserDetailServer(userId: string): Promise<User> {
  const dto = await apiServerFetch<UserRead>({ url: `/users/${userId}`, method: "GET" });
  return toUser(dto);
}
