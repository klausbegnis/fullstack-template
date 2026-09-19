import type { UserRead } from "@/lib/api/generated/model";
import type { User } from "@/features/users/model/user";

/**
 * Maps the FastAPI representation of a user to the domain `User`. This is
 * the only place `snake_case` field names appear.
 */
export function toUser(dto: UserRead): User {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    role: dto.role,
    disabledAt: dto.disabled_at ? new Date(dto.disabled_at) : null,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  };
}
