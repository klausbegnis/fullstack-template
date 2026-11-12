import type { ReactNode } from "react";
import { displayNameOf, type User } from "@/features/users/model/user";

export interface UserDetailViewProps {
  user: User;
  editForm: ReactNode;
  disableControl: ReactNode;
}

/**
 * Renders a user's details, from props only, with the edit form and the
 * disable control rendered wherever their containers placed them.
 */
export function UserDetailView({ user, editForm, disableControl }: UserDetailViewProps) {
  return (
    <div className="flex max-w-lg flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-gray-900">{displayNameOf(user)}</h1>
        <p className="text-sm text-gray-600">{user.email}</p>
        <p className="text-sm text-gray-600">
          {user.role} · {user.disabledAt ? "Disabled" : "Active"}
        </p>
      </div>
      {editForm}
      {user.disabledAt ? null : disableControl}
    </div>
  );
}
