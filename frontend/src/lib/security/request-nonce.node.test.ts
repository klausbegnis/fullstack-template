import { describe, expect, it, vi } from "vitest";

const incoming = vi.hoisted(() => ({ headers: new Headers() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  headers: async () => incoming.headers,
}));

import { readRequestNonce } from "@/lib/security/request-nonce";

describe("readRequestNonce", () => {
  it("returns the nonce the middleware put on the request", async () => {
    incoming.headers = new Headers({ "x-nonce": "abc123==" });

    await expect(readRequestNonce()).resolves.toBe("abc123==");
  });

  it("returns null when the request carries no nonce", async () => {
    incoming.headers = new Headers();

    await expect(readRequestNonce()).resolves.toBeNull();
  });
});
