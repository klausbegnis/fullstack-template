"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useDisableUser } from "@/features/users/api/use-disable-user";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useModalDialog } from "@/components/ui/use-modal-dialog";

export interface DisableUserButtonProps {
  userId: string;
}

/**
 * Asks for confirmation in a modal `Dialog`, then disables the user through
 * `useMutation` and refreshes the current route so the server-rendered
 * chrome reflects the new status. The dialog cannot be dismissed while the
 * request is in flight.
 */
export function DisableUserButton({ userId }: DisableUserButtonProps) {
  const router = useRouter();
  const mutation = useDisableUser();
  const [confirming, setConfirming] = useState(false);
  const close = () => {
    if (!mutation.isPending) setConfirming(false);
  };
  const dialogRef = useModalDialog(confirming, close, { initialFocus: "button[data-cancel]" });

  const confirm = async () => {
    await mutation.mutateAsync(userId);
    setConfirming(false);
    router.refresh();
  };

  return (
    <>
      <Button type="button" variant="danger" onClick={() => setConfirming(true)}>
        Disable user
      </Button>
      <Dialog
        dialogRef={dialogRef}
        title="Disable this user?"
        description="They will no longer be able to sign in."
        onClose={close}
        className="m-auto w-[calc(100%_-_2rem)] max-w-md rounded-2xl border border-gray-200 bg-white p-0 shadow-2xl"
      >
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            data-cancel=""
            disabled={mutation.isPending}
            onClick={close}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="danger"
            disabled={mutation.isPending}
            onClick={() => void confirm()}
          >
            {mutation.isPending ? "Disabling…" : "Disable"}
          </Button>
        </div>
      </Dialog>
    </>
  );
}
