import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { accessTokenExpiresAt } from "@/lib/auth/access-expiry";

function tokenWith(claims: unknown): string {
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `header.${payload}.signature`;
}

describe("accessTokenExpiresAt", () => {
  it("reads the exp claim as epoch milliseconds", () => {
    expect(accessTokenExpiresAt(tokenWith({ sub: "u1", exp: 1_793_000_000 }))).toBe(
      1_793_000_000_000,
    );
  });

  it.each([
    undefined,
    "",
    "not-a-jwt",
    "header.%%%.signature",
    tokenWith({ sub: "u1" }),
    tokenWith({ exp: "soon" }),
    tokenWith(null),
  ])("returns null for %s", (token) => {
    expect(accessTokenExpiresAt(token)).toBeNull();
  });
});
