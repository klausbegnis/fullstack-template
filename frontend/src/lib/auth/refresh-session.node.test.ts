import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const browserDocument = vi.hoisted(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://app.test/api");
  return { cookie: "" };
});

import { onLoggedOut, refreshSession, subscribeAuthChannel } from "@/lib/auth/refresh-session";
import type { AuthChannelMessage } from "@/lib/auth/refresh-session";

const ACCESS_EXPIRES_AT = "2026-10-29T21:15:00Z";

const server = setupServer();

function setCsrfCookie(value: string) {
  browserDocument.cookie = `app_csrf=${value}`;
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

function expiryResponse() {
  return HttpResponse.json({
    access_expires_at: ACCESS_EXPIRES_AT,
    session_expires_at: "2026-11-28T21:00:00Z",
  });
}

function unauthorized(code = "unauthorized") {
  return HttpResponse.json(
    { success: false, error: { code, message: "Authentication required", details: null } },
    { status: 401 },
  );
}

function listenToOtherTab(): AuthChannelMessage[] {
  const received: AuthChannelMessage[] = [];
  const otherTab = new BroadcastChannel("auth");
  otherTab.addEventListener("message", (event: MessageEvent<AuthChannelMessage>) => {
    received.push(event.data);
  });
  cleanups.push(() => otherTab.close());
  return received;
}

const cleanups: (() => void)[] = [];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

beforeEach(() => {
  vi.stubGlobal("document", browserDocument);
  setCsrfCookie("csrf-1");
});

afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  server.resetHandlers();
  vi.unstubAllGlobals();
});

describe("refreshSession", () => {
  it("shares one request between concurrent callers in a tab", async () => {
    const refresh = serveRefresh(expiryResponse);

    const [first, second] = await Promise.all([refreshSession(), refreshSession()]);

    expect(refresh.calls).toBe(1);
    expect(first).toEqual({
      status: "refreshed",
      accessExpiresAt: Date.parse(ACCESS_EXPIRES_AT),
    });
    expect(second).toBe(first);
  });

  it("skips the request when another tab rotated the CSRF cookie while it waited", async () => {
    const refresh = serveRefresh(expiryResponse);
    vi.stubGlobal("navigator", {
      locks: {
        request: async (_name: string, task: () => Promise<unknown>) => {
          setCsrfCookie("csrf-rotated-by-another-tab");
          return task();
        },
      },
    });

    const outcome = await refreshSession();

    expect(refresh.calls).toBe(0);
    expect(outcome).toEqual({ status: "refreshed", accessExpiresAt: null });
  });

  it("announces the new expiry to the other tabs", async () => {
    serveRefresh(expiryResponse);
    const received = listenToOtherTab();

    await refreshSession();

    await vi.waitFor(() =>
      expect(received).toEqual([{ type: "refreshed", expiresAt: Date.parse(ACCESS_EXPIRES_AT) }]),
    );
  });

  it("treats a rotation a sibling request won as refreshed and keeps the session", async () => {
    serveRefresh(() => unauthorized("refresh_superseded"));
    const loggedOut = vi.fn();
    cleanups.push(onLoggedOut(loggedOut));

    const outcome = await refreshSession();

    expect(outcome).toEqual({ status: "refreshed", accessExpiresAt: null });
    expect(loggedOut).not.toHaveBeenCalled();
  });

  it("ends the session in this tab and announces it when the refresh is refused", async () => {
    serveRefresh(() => unauthorized());
    const received = listenToOtherTab();
    const loggedOut = vi.fn();
    cleanups.push(onLoggedOut(loggedOut));

    const outcome = await refreshSession();

    expect(outcome).toEqual({ status: "logged-out" });
    expect(loggedOut).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(received).toEqual([{ type: "logged-out" }]));
  });

  it("reports an unreachable API without ending the session", async () => {
    serveRefresh(() => HttpResponse.error());
    const loggedOut = vi.fn();
    cleanups.push(onLoggedOut(loggedOut));

    const outcome = await refreshSession();

    expect(outcome).toEqual({ status: "unavailable" });
    expect(loggedOut).not.toHaveBeenCalled();
  });

  it("delivers what another tab announces to subscribers", async () => {
    const received: AuthChannelMessage[] = [];
    cleanups.push(subscribeAuthChannel((message) => received.push(message)));
    const otherTab = new BroadcastChannel("auth");
    cleanups.push(() => otherTab.close());

    otherTab.postMessage({ type: "refreshed", expiresAt: 42 });
    otherTab.postMessage({ type: "unknown" });
    otherTab.postMessage({ type: "logged-out" });

    await vi.waitFor(() =>
      expect(received).toEqual([{ type: "refreshed", expiresAt: 42 }, { type: "logged-out" }]),
    );
  });
});
