import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { NextRequest } from "next/server";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { GET } from "@/app/api/auth/renew/route";

const ORIGIN = "http://localhost:3000";
const API = "http://localhost:8000";
const ROTATED_COOKIES = [
  "app_access=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax",
  "app_refresh=new-refresh; HttpOnly; Max-Age=1209600; Path=/api/auth; SameSite=lax",
  "app_csrf=new-csrf; Max-Age=1209600; Path=/; SameSite=lax",
];
const server = setupServer();

interface RenewRequestOptions {
  next?: string;
  secFetchSite?: string | null;
  referer?: string;
  cookies?: string;
}

function renewRequest({
  next = "/users?page=2",
  secFetchSite = "same-origin",
  referer,
  cookies = "app_refresh=refresh-1; app_csrf=csrf-1",
}: RenewRequestOptions = {}) {
  const headers = new Headers({ cookie: cookies, host: "localhost:3000" });
  if (secFetchSite) headers.set("sec-fetch-site", secFetchSite);
  if (referer) headers.set("referer", referer);
  const url = new URL("/api/auth/renew", ORIGIN);
  url.searchParams.set("next", next);
  return new NextRequest(url, { headers });
}

function serveRefresh(respond: () => Response): Headers[] {
  const seen: Headers[] = [];
  server.use(
    http.post(`${API}/auth/refresh`, ({ request }) => {
      seen.push(request.headers);
      return respond();
    }),
  );
  return seen;
}

function rotated() {
  const headers = new Headers();
  for (const cookie of ROTATED_COOKIES) headers.append("set-cookie", cookie);
  return HttpResponse.json(
    { access_expires_at: "2026-10-29T21:15:00Z", session_expires_at: "2026-11-28T21:00:00Z" },
    { headers },
  );
}

function refused(code: string) {
  return () =>
    HttpResponse.json(
      { success: false, error: { code, message: "Authentication required" } },
      { status: 401 },
    );
}

describe("GET /api/auth/renew", () => {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it.each(["cross-site", "same-site"])(
    "refuses a navigation whose Sec-Fetch-Site is %s",
    async (secFetchSite) => {
      const response = await GET(renewRequest({ secFetchSite }));

      expect(response.status).toBe(403);
    },
  );

  it("refuses a request without fetch metadata that another site referred", async () => {
    const response = await GET(
      renewRequest({ secFetchSite: null, referer: "https://evil.example/page" }),
    );

    expect(response.status).toBe(403);
  });

  it("renews a request without fetch metadata from this origin or the address bar", async () => {
    serveRefresh(() =>
      HttpResponse.json({
        access_expires_at: "2026-10-29T21:15:00Z",
        session_expires_at: "2026-11-28T21:00:00Z",
      }),
    );

    const referred = await GET(renewRequest({ secFetchSite: null, referer: `${ORIGIN}/users` }));
    const typed = await GET(renewRequest({ secFetchSite: null }));

    expect([referred.status, typed.status]).toEqual([303, 303]);
    expect(typed.headers.get("location")).toBe("/users?page=2");
  });

  it("renews with the visitor's cookies and CSRF token and returns to the same page", async () => {
    const seen = serveRefresh(rotated);

    const response = await GET(renewRequest());

    expect(seen).toHaveLength(1);
    expect(seen[0]?.get("cookie")).toBe("app_refresh=refresh-1; app_csrf=csrf-1");
    expect(seen[0]?.get("x-csrf-token")).toBe("csrf-1");
    expect(seen[0]?.get("origin")).toBe(ORIGIN);
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/users?page=2");
    const cookies = response.headers.getSetCookie();
    expect(cookies).toEqual([
      ...ROTATED_COOKIES,
      "app_renewed=1; Path=/; Max-Age=10; HttpOnly; SameSite=Lax",
    ]);
  });

  it.each(["//evil.example", "https://evil.example/users", "/\\evil.example"])(
    "never returns off-site for next=%s",
    async (next) => {
      serveRefresh(rotated);

      const response = await GET(renewRequest({ next }));

      expect(response.headers.get("location")).toBe("/");
    },
  );

  it("returns to the page with only the loop guard when a sibling request won the rotation", async () => {
    serveRefresh(refused("refresh_superseded"));
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const pending = GET(renewRequest());
    await vi.advanceTimersByTimeAsync(1_000);
    const response = await pending;
    vi.useRealTimers();

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/users?page=2");
    expect(response.headers.getSetCookie()).toEqual([
      "app_renewed=1; Path=/; Max-Age=10; HttpOnly; SameSite=Lax",
    ]);
  });

  it("clears the session cookies and shows the expired notice when the session ended", async () => {
    serveRefresh(refused("unauthorized"));

    const response = await GET(renewRequest());

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/login?next=%2Fusers%3Fpage%3D2&reason=expired");
    expect(response.headers.getSetCookie()).toEqual([
      "app_access=; Path=/; Max-Age=0",
      "app_refresh=; Path=/api/auth; Max-Age=0",
      "app_csrf=; Path=/; Max-Age=0",
    ]);
  });

  it("ends the session without calling the API when no CSRF cookie is left", async () => {
    const response = await GET(renewRequest({ cookies: "app_refresh=refresh-1" }));

    expect(response.headers.get("location")).toBe("/login?next=%2Fusers%3Fpage%3D2&reason=expired");
  });

  it("keeps the cookies and goes to the login page when the API is down", async () => {
    serveRefresh(() => HttpResponse.json({}, { status: 502 }));

    const response = await GET(renewRequest());

    expect(response.headers.get("location")).toBe("/login?next=%2Fusers%3Fpage%3D2");
    expect(response.headers.getSetCookie()).toEqual([]);
  });
});
