import { useMutation, useQueryClient } from "@tanstack/react-query";
import { disableUserUsersUserIdDelete } from "@/lib/api/generated/endpoints/users/users";
import { userQueries } from "@/features/users/api/user-queries";

/**
 * Disables a user (a soft delete on the backend) and invalidates every
 * cached user list and that user's detail entry.
 */
export function useDisableUser() {
  const queryClient = useQueryClient();
  return useMutation<void, unknown, string>({
    mutationFn: (userId) => disableUserUsersUserIdDelete(userId),
    onSuccess: (_result, userId) => {
      void queryClient.invalidateQueries({ queryKey: userQueries.lists() });
      void queryClient.invalidateQueries({ queryKey: userQueries.detail(userId).queryKey });
    },
  });
}
