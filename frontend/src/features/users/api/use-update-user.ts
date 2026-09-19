"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateUserUsersUserIdPatch } from "@/lib/api/generated/endpoints/users/users";
import { unwrapGenerated } from "@/lib/api/unwrap-generated";
import { toUser } from "@/features/users/api/user-mapper";
import { userQueries } from "@/features/users/api/user-queries";
import type { UserRead } from "@/lib/api/generated/model";
import type { UpdateUserValues } from "@/features/users/model/user-schema";
import type { User } from "@/features/users/model/user";

export interface UpdateUserVariables {
  userId: string;
  values: UpdateUserValues;
}

/**
 * Updates a user and invalidates both its detail cache entry and every
 * cached user list, since the edited fields (name, email, role) are shown
 * in both.
 */
export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation<User, unknown, UpdateUserVariables>({
    mutationFn: async ({ userId, values }) => {
      const dto = unwrapGenerated<UserRead>(await updateUserUsersUserIdPatch(userId, values));
      return toUser(dto);
    },
    onSuccess: (_user, { userId }) => {
      void queryClient.invalidateQueries({ queryKey: userQueries.lists() });
      void queryClient.invalidateQueries({ queryKey: userQueries.detail(userId).queryKey });
    },
  });
}
