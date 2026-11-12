import { describe, expect, it } from "vitest";
import { canRenewFrom, renewPathReturningTo, shouldRenew } from "@/lib/auth/renewal";

describe("canRenewFrom", () => {
  it("refuses another site and accepts same-origin, address-bar or unlabelled requests", () => {
    expect(canRenewFrom("same-origin")).toBe(true);
    expect(canRenewFrom("none")).toBe(true);
    expect(canRenewFrom("same-site")).toBe(false);
    expect(canRenewFrom("cross-site")).toBe(false);
    expect(canRenewFrom(null)).toBe(true);
  });
});

describe("shouldRenew", () => {
  const renewable = { hasCsrfCookie: true, hasRenewedCookie: false, secFetchSite: "none" };

  it("renews a same-origin visitor who still holds a session", () => {
    expect(shouldRenew(renewable)).toBe(true);
  });

  it("does not renew without a session, right after a renewal, or from another site", () => {
    expect(shouldRenew({ ...renewable, hasCsrfCookie: false })).toBe(false);
    expect(shouldRenew({ ...renewable, hasRenewedCookie: true })).toBe(false);
    expect(shouldRenew({ ...renewable, secFetchSite: "cross-site" })).toBe(false);
  });
});

describe("renewPathReturningTo", () => {
  it("encodes the path and query to return to", () => {
    expect(renewPathReturningTo("/users?page=2")).toBe("/api/auth/renew?next=%2Fusers%3Fpage%3D2");
  });
});
