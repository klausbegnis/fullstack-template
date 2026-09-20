import { nextId } from "@/testing/factories";
import type { PaginatedResponseUserRead, UserRead } from "@/lib/api/generated/model";
import type { User } from "@/features/users/model/user";

const FIXED_TIMESTAMP = "2026-01-01T00:00:00Z";

/**
 * Builds the backend `snake_case` shape of a user, typed from the generated
 * `UserRead` DTO so a schema change breaks the fixtures rather than the
 * assertions. Use it for MSW handler payloads.
 */
export function buildUserDto(overrides: Partial<UserRead> = {}): UserRead {
  return {
    id: nextId(),
    name: "Ada Lovelace",
    email: `ada-${nextId()}@example.com`,
    role: "admin",
    disabled_at: null,
    created_at: FIXED_TIMESTAMP,
    updated_at: FIXED_TIMESTAMP,
    ...overrides,
  };
}

/**
 * Builds a domain `User`, the shape components and containers receive once
 * `toUser` has mapped the DTO.
 */
export function buildUser(overrides: Partial<User> = {}): User {
  return {
    id: nextId(),
    name: "Ada Lovelace",
    email: `ada-${nextId()}@example.com`,
    role: "admin",
    disabledAt: null,
    createdAt: new Date(FIXED_TIMESTAMP),
    updatedAt: new Date(FIXED_TIMESTAMP),
    ...overrides,
  };
}

/**
 * Wraps user DTOs in the backend's paginated envelope, so an MSW handler for
 * `GET /users` can return exactly what FastAPI returns.
 */
export function buildPaginatedUsersDto(
  items: UserRead[],
  overrides: Partial<PaginatedResponseUserRead> = {},
): PaginatedResponseUserRead {
  return {
    success: true,
    data: items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...overrides,
  };
}
