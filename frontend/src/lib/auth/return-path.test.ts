import { describe, expect, it } from "vitest";
import { expiredLoginPath, loginPathReturningTo, safeReturnPath } from "@/lib/auth/return-path";

describe("safeReturnPath", () => {
  it("keeps a same-origin path with its query", () => {
    expect(safeReturnPath("/users?page=2&role=admin")).toBe("/users?page=2&role=admin");
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "evil.example/path",
    "/\tevil",
    "/..//evil.example",
    "/.//evil.example",
    "/%2e%2e//evil.example",
    "/a/..//evil.example",
    "",
  ])("rejects %s", (value) => {
    expect(safeReturnPath(value)).toBeNull();
  });

  it("rejects a missing or over-long value", () => {
    expect(safeReturnPath(undefined)).toBeNull();
    expect(safeReturnPath(null)).toBeNull();
    expect(safeReturnPath(`/${"a".repeat(2048)}`)).toBeNull();
  });
});

describe("loginPathReturningTo", () => {
  it("encodes the return path into the next parameter", () => {
    expect(loginPathReturningTo("/users?page=2&role=admin")).toBe(
      "/login?next=%2Fusers%3Fpage%3D2%26role%3Dadmin",
    );
  });
});

describe("expiredLoginPath", () => {
  it("returns to the page and asks for the expired notice", () => {
    expect(expiredLoginPath("/users?page=2")).toBe(
      "/login?next=%2Fusers%3Fpage%3D2&reason=expired",
    );
  });
});
