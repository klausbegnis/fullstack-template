import { describe, expect, it } from "vitest";
import { toUser } from "@/features/users/api/user-mapper";

describe("toUser", () => {
  it("maps the FastAPI representation of an active user", () => {
    const user = toUser({
      id: "a1",
      name: "Ada Lovelace",
      email: "ada@example.com",
      role: "admin",
      disabled_at: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    });

    expect(user).toEqual({
      id: "a1",
      name: "Ada Lovelace",
      email: "ada@example.com",
      role: "admin",
      disabledAt: null,
      createdAt: new Date("2026-01-01T00:00:00Z"),
      updatedAt: new Date("2026-01-02T00:00:00Z"),
    });
  });

  it("maps a disabled user's disabled_at to a Date", () => {
    const user = toUser({
      id: "a2",
      name: "Grace Hopper",
      email: "grace@example.com",
      role: "member",
      disabled_at: "2026-02-01T00:00:00Z",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    });

    expect(user.disabledAt).toEqual(new Date("2026-02-01T00:00:00Z"));
  });
});
