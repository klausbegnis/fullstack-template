export type UserRole = "admin" | "member";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  disabledAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface UsersPage {
  items: User[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/**
 * The name to show for a user: their name, or the local part of their email when the name is
 * blank, as the API's `/auth/me` does for an administrator created by `bootstrap_admin`.
 */
export function displayNameOf(user: Pick<User, "name" | "email">): string {
  return user.name.trim() || (user.email.split("@", 1)[0] ?? user.email);
}
