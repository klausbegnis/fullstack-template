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
