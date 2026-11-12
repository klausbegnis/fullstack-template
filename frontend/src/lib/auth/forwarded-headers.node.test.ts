import { beforeEach, describe, expect, it, vi } from "vitest";

const incoming = vi.hoisted(() => ({ headers: new Headers() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: async () => incoming.headers }));

import { browserOriginHeaders, forwardedJsonHeaders } from "@/lib/auth/forwarded-headers";

describe("browserOriginHeaders", () => {
  beforeEach(() => {
    incoming.headers = new Headers();
  });

  it("returns the browser's Origin and Referer", async () => {
    incoming.headers = new Headers({
      origin: "http://localhost:3000",
      referer: "http://localhost:3000/users?page=2",
      cookie: "app_access=token",
    });

    await expect(browserOriginHeaders()).resolves.toEqual({
      origin: "http://localhost:3000",
      referer: "http://localhost:3000/users?page=2",
    });
  });

  it("returns nothing when the browser sent neither", async () => {
    await expect(browserOriginHeaders()).resolves.toEqual({});
  });
});

describe("forwardedJsonHeaders", () => {
  it("never carries the browser's Origin to a public auth endpoint", async () => {
    incoming.headers = new Headers({
      origin: "http://localhost:3000",
      "x-forwarded-for": "1.2.3.4",
    });

    const forwarded = await forwardedJsonHeaders();

    expect(forwarded).not.toHaveProperty("origin");
    expect(forwarded["x-forwarded-for"]).toBe("1.2.3.4");
  });
});

describe("forwardedJsonHeaders client address", () => {
  it("carries the edge proxy's X-Real-IP", async () => {
    incoming.headers = new Headers({ "x-real-ip": "203.0.113.7" });

    const forwarded = await forwardedJsonHeaders();

    expect(forwarded["x-real-ip"]).toBe("203.0.113.7");
    expect(forwarded["Content-Type"]).toBe("application/json");
  });
});
