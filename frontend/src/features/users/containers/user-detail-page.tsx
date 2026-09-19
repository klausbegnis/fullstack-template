"use client";

import { useQuery } from "@tanstack/react-query";
import { userQueries } from "@/features/users/api/user-queries";
import { UserDetailView } from "@/features/users/components/user-detail-view";
import { EditUserForm } from "@/features/users/containers/edit-user-form";
import { DisableUserButton } from "@/features/users/containers/disable-user-button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export interface UserDetailPageProps {
  userId: string;
}

/**
 * Wires the user detail query to the presentational view, and to the edit
 * and disable containers. Prefetched server-side by
 * `app/(app)/users/[userId]/page.tsx`.
 */
export function UserDetailPage({ userId }: UserDetailPageProps) {
  const { data, isPending, isError } = useQuery(userQueries.detail(userId));

  if (isPending) {
    return (
      <div className="flex justify-center p-12">
        <Spinner label="Loading user" />
      </div>
    );
  }

  if (isError || !data) {
    return <Alert tone="danger" title="Failed to load user" />;
  }

  return (
    <UserDetailView
      user={data}
      editForm={<EditUserForm user={data} />}
      disableControl={<DisableUserButton userId={data.id} />}
    />
  );
}
