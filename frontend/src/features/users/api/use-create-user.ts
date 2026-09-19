"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createUserUsersPost } from "@/lib/api/generated/endpoints/users/users";
import { unwrapGenerated } from "@/lib/api/unwrap-generated";
import { toUser } from "@/features/users/api/user-mapper";
import { userQueries } from "@/features/users/api/user-queries";
import type { UserRead } from "@/lib/api/generated/model";
import type { CreateUserValues } from "@/features/users/model/user-schema";
import type { User } from "@/features/users/model/user";

/**
 * Creates a user and invalidates every cached user list so the new row
 * appears without a manual refetch.
 */
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation<User, unknown, CreateUserValues>({
    mutationFn: async (values) => {
      const dto = unwrapGenerated<UserRead>(await createUserUsersPost(values));
      return toUser(dto);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userQueries.lists() });
    },
  });
}
