import Link from "next/link";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination, type PaginationProps } from "@/components/ui/pagination";
import { PILL_CLASS } from "@/components/ui/pill";
import { Spinner } from "@/components/ui/spinner";
import type { User } from "@/features/users/model/user";

/** The id of the list's heading, which the pager scrolls into view on a page change. */
export const USERS_HEADING_ID = "users-heading";

export type UsersPagerProps = Pick<
  PaginationProps,
  "page" | "pageCount" | "totalItems" | "pageSize" | "onPageChange" | "navRef"
>;

export interface UsersListViewProps {
  users: readonly User[];
  status: "loading" | "error" | "ready";
  pager: UsersPagerProps;
}

/**
 * Renders the users table, the shared pager and the link to create a user,
 * from props only, or an empty state when there are no users yet. It carries
 * no `'use client'` directive and still renders on the server — code crosses
 * through imports, data crosses through props.
 */
export function UsersListView({ users, status, pager }: UsersListViewProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 id={USERS_HEADING_ID} className="text-lg font-semibold text-gray-900">
          Users
        </h1>
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

      {status === "ready" && users.length === 0 ? (
        <EmptyState
          title="No users yet"
          description="Users you create show up here."
          action={
            <Link href="/users/new">
              <Button>Create the first user</Button>
            </Link>
          }
        />
      ) : null}

      {status === "ready" && users.length > 0 ? (
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
                  <td className="py-2">
                    <span className={PILL_CLASS}>{user.disabledAt ? "Disabled" : "Active"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <Pagination {...pager} itemLabel="users" label="Users pagination" />
        </>
      ) : null}
    </div>
  );
}
