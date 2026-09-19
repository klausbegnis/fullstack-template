import Link from "next/link";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { User } from "@/features/users/model/user";

export interface UsersListViewProps {
  users: readonly User[];
  status: "loading" | "error" | "ready";
  page: number;
  totalPages: number;
  canGoToPreviousPage: boolean;
  canGoToNextPage: boolean;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

/**
 * Renders the users table, its pagination controls and the link to create a
 * user, from props only. It carries no `'use client'` directive and still
 * renders on the server — code crosses through imports, data crosses
 * through props.
 */
export function UsersListView({
  users,
  status,
  page,
  totalPages,
  canGoToPreviousPage,
  canGoToNextPage,
  onPreviousPage,
  onNextPage,
}: UsersListViewProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">Users</h1>
        <Link href="/users/new">
          <Button>New user</Button>
        </Link>
      </div>

      {status === "loading" ? (
        <div className="flex justify-center p-12">
          <Spinner label="Loading users" />
        </div>
      ) : null}

      {status === "error" ? <Alert tone="danger" title="Failed to load users" /> : null}

      {status === "ready" ? (
        <>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500">
                <th scope="col" className="py-2 font-medium">
                  Name
                </th>
                <th scope="col" className="py-2 font-medium">
                  Email
                </th>
                <th scope="col" className="py-2 font-medium">
                  Role
                </th>
                <th scope="col" className="py-2 font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-gray-100">
                  <td className="py-2">
                    <Link href={`/users/${user.id}`} className="text-blue-600 hover:underline">
                      {user.name}
                    </Link>
                  </td>
                  <td className="py-2 text-gray-700">{user.email}</td>
                  <td className="py-2 text-gray-700">{user.role}</td>
                  <td className="py-2 text-gray-700">{user.disabledAt ? "Disabled" : "Active"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="secondary"
              disabled={!canGoToPreviousPage}
              {...{ onClick: onPreviousPage }}
            >
              Previous
            </Button>
            <span className="text-sm text-gray-500">
              Page {page} of {totalPages || 1}
            </span>
            <Button
              type="button"
              variant="secondary"
              disabled={!canGoToNextPage}
              {...{ onClick: onNextPage }}
            >
              Next
            </Button>
          </div>
        </>
      ) : null}
    </div>
  );
}
