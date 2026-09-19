import { describe, expect, it } from "vitest";
import { createUserSchema, updateUserSchema } from "@/features/users/model/user-schema";

describe("createUserSchema", () => {
  it("accepts a valid payload and defaults the role to member", () => {
    const result = createUserSchema.parse({
      name: "Ada Lovelace",
      email: "ada@example.com",
      password: "secret",
    });
    expect(result.role).toBe("member");
  });

  it("rejects an empty name with a readable message", () => {
    const result = createUserSchema.safeParse({
      name: "",
      email: "ada@example.com",
      password: "secret",
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe("Name is required");
  });

  it("rejects a malformed email", () => {
    const result = createUserSchema.safeParse({
      name: "Ada Lovelace",
      email: "not-an-email",
      password: "secret",
    });
    expect(result.success).toBe(false);
  });
});

describe("updateUserSchema", () => {
  it("accepts a full replacement payload", () => {
    const result = updateUserSchema.safeParse({
      name: "Ada Lovelace",
      email: "ada@example.com",
      role: "admin",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an invalid role", () => {
    const result = updateUserSchema.safeParse({
      name: "Ada Lovelace",
      email: "ada@example.com",
      role: "superuser",
    });
    expect(result.success).toBe(false);
  });
});
