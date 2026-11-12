import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const incoming = vi.hoisted(() => ({
  headers: new Headers(),
  deleted: [] as string[],
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    toString: () => "app_access=token; app_csrf=csrf-token",
    get: (name: string) => (name === "app_csrf" ? { value: "csrf-token" } : undefined),
    delete: ({ name }: { name: string }) => incoming.deleted.push(name),
  }),
  headers: async () => incoming.headers,
}));

import { apiServerFetch } from "@/lib/api/server-client";
import { endSession } from "@/lib/auth/end-session";

const API = "http://localhost:8000";
const server = setupServer();

function recordRequests(method: "get" | "post", path: string): Headers[] {
  const seen: Headers[] = [];
  server.use(
    http[method](`${API}${path}`, ({ request }) => {
      seen.push(request.headers);
      return method === "post"
        ? new HttpResponse(null, { status: 204 })
        : HttpResponse.json({ success: true, message: "ok", data: null });
    }),
  );
  return seen;
}

describe("endSession", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
  beforeEach(() => {
    incoming.deleted = [];
    incoming.headers = new Headers({
      origin: "http://localhost:3000",
      referer: "http://localhost:3000/users",
    });
  });

  it("forwards the browser's Origin, Referer, cookies and CSRF token to the logout", async () => {
    const seen = recordRequests("post", "/auth/logout");

    await endSession();

    expect(seen).toHaveLength(1);
    expect(seen[0]?.get("origin")).toBe("http://localhost:3000");
    expect(seen[0]?.get("referer")).toBe("http://localhost:3000/users");
    expect(seen[0]?.get("cookie")).toBe("app_access=token; app_csrf=csrf-token");
    expect(seen[0]?.get("x-csrf-token")).toBe("csrf-token");
    expect(incoming.deleted).toEqual(["app_access", "app_refresh", "app_csrf"]);
  });

  it("sends no Origin when the browser request carried none", async () => {
    incoming.headers = new Headers();
    const seen = recordRequests("post", "/auth/logout");

    await endSession();

    expect(seen[0]?.has("origin")).toBe(false);
    expect(seen[0]?.has("referer")).toBe(false);
  });

  it("does not forward the browser's Origin on a server-side read", async () => {
    const seen = recordRequests("get", "/auth/me");

    await apiServerFetch({ url: "/auth/me", method: "GET" });

    expect(seen[0]?.has("origin")).toBe(false);
    expect(seen[0]?.get("cookie")).toBe("app_access=token; app_csrf=csrf-token");
  });
});
