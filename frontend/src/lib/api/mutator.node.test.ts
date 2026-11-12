import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const browserDocument = vi.hoisted(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://app.test/api");
  return { cookie: "" };
});

import { apiMutator } from "@/lib/api/mutator";
import { onLoggedOut } from "@/lib/auth/refresh-session";
import { ApiError } from "@/lib/errors/api-error";

const server = setupServer();

function setCsrfCookie(value: string) {
  browserDocument.cookie = `app_csrf=${value}`;
}

function unauthorized() {
  return HttpResponse.json(
    { success: false, error: { code: "unauthorized", message: "Authentication required" } },
    { status: 401 },
  );
}

function ok(data: unknown) {
  return HttpResponse.json({ success: true, message: "ok", data });
}

function serveRefresh(respond: () => Response): { calls: number } {
  const counter = { calls: 0 };
  server.use(
    http.post("*/auth/refresh", () => {
      counter.calls += 1;
      return respond();
    }),
  );
  return counter;
}

function rotatingRefresh() {
  setCsrfCookie("csrf-rotated");
  return HttpResponse.json({
    access_expires_at: "2026-10-29T21:15:00Z",
    session_expires_at: "2026-11-28T21:00:00Z",
  });
}

const stopHandlers: (() => void)[] = [];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

beforeEach(() => {
  vi.stubGlobal("document", browserDocument);
  setCsrfCookie("csrf-1");
});

afterEach(() => {
  for (const stop of stopHandlers.splice(0)) stop();
  server.resetHandlers();
  vi.unstubAllGlobals();
});

describe("apiMutator after a 401", () => {
  it("refreshes once and retries the request once", async () => {
    let attempts = 0;
    server.use(
      http.get("*/users", () => {
        attempts += 1;
        return attempts === 1 ? unauthorized() : ok([{ id: "u1" }]);
      }),
    );
    const refresh = serveRefresh(rotatingRefresh);

    const result = await apiMutator<{ id: string }[]>("/users");

    expect(result).toEqual([{ id: "u1" }]);
    expect(attempts).toBe(2);
    expect(refresh.calls).toBe(1);
  });

  it("sends the rotated CSRF token on the retried mutation", async () => {
    const csrfTokens: (string | null)[] = [];
    server.use(
      http.post("*/users", ({ request }) => {
        csrfTokens.push(request.headers.get("x-csrf-token"));
        return csrfTokens.length === 1 ? unauthorized() : ok({ id: "u1" });
      }),
    );
    serveRefresh(rotatingRefresh);

    await apiMutator("/users", { method: "POST", body: JSON.stringify({ name: "Ada" }) });

    expect(csrfTokens).toEqual(["csrf-1", "csrf-rotated"]);
  });

  it("does not retry when the session cannot be renewed and hands over to logout", async () => {
    let attempts = 0;
    server.use(
      http.get("*/users", () => {
        attempts += 1;
        return unauthorized();
      }),
    );
    const refresh = serveRefresh(unauthorized);
    const loggedOut = vi.fn();
    stopHandlers.push(onLoggedOut(loggedOut));

    await expect(apiMutator("/users")).rejects.toMatchObject({ status: 401 });

    expect(attempts).toBe(1);
    expect(refresh.calls).toBe(1);
    expect(loggedOut).toHaveBeenCalledTimes(1);
  });

  it("surfaces a second 401 instead of refreshing again", async () => {
    let attempts = 0;
    server.use(
      http.get("*/users", () => {
        attempts += 1;
        return unauthorized();
      }),
    );
    const refresh = serveRefresh(rotatingRefresh);

    await expect(apiMutator("/users")).rejects.toBeInstanceOf(ApiError);

    expect(attempts).toBe(2);
    expect(refresh.calls).toBe(1);
  });

  it.each(["/auth/login", "/auth/logout"])("never refreshes after a 401 from %s", async (path) => {
    server.use(http.post(`*${path}`, unauthorized));
    const refresh = serveRefresh(rotatingRefresh);

    await expect(apiMutator(path, { method: "POST" })).rejects.toMatchObject({ status: 401 });

    expect(refresh.calls).toBe(0);
  });

  it("never retries a refused refresh", async () => {
    const refresh = serveRefresh(unauthorized);

    await expect(apiMutator("/auth/refresh", { method: "POST" })).rejects.toMatchObject({
      status: 401,
    });

    expect(refresh.calls).toBe(1);
  });
});
