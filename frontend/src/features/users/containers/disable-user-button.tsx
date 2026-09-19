"use client";

import { useRouter } from "next/navigation";
import { useDisableUser } from "@/features/users/api/use-disable-user";
import { Button } from "@/components/ui/button";

export interface DisableUserButtonProps {
  userId: string;
}

/**
 * Disables a user through `useMutation`, then refreshes the current route
 * so the server-rendered chrome reflects the new status.
 */
export function DisableUserButton({ userId }: DisableUserButtonProps) {
  const router = useRouter();
  const mutation = useDisableUser();

  const handleClick = async () => {
    await mutation.mutateAsync(userId);
    router.refresh();
  };

  return (
    <Button
      type="button"
      variant="danger"
      disabled={mutation.isPending}
      onClick={() => void handleClick()}
    >
      {mutation.isPending ? "Disabling…" : "Disable user"}
    </Button>
  );
}
