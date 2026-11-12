import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { middleware } from "@/middleware";

const ORIGIN = "http://localhost:3000";

function requestFor(pathname: string, { withSession }: { withSession: boolean }) {
  const request = new NextRequest(new URL(pathname, ORIGIN));
  if (withSession) {
    request.cookies.set("app_access", "token");
  }
  return request;
}

function lapsedRequest(
  path: string,
  { cookies, secFetchSite }: { cookies: string[]; secFetchSite: string },
) {
  const request = new NextRequest(new URL(path, ORIGIN), {
    headers: { "sec-fetch-site": secFetchSite },
  });
  for (const name of cookies) request.cookies.set(name, "value");
  return request;
}

function scriptSources(policy: string | null): string {
  return (
    policy
      ?.split("; ")
      .find((entry) => entry.startsWith("script-src "))
      ?.slice("script-src ".length) ?? ""
  );
}

function nonceOf(policy: string | null): string | undefined {
  return /'nonce-([^']+)'/.exec(scriptSources(policy))?.[1];
}

describe("middleware", () => {
  it("sends an anonymous visitor on a protected page to /login", () => {
    const response = middleware(requestFor("/users", { withSession: false }));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(`${ORIGIN}/login`);
  });

  it("lets an anonymous visitor see /login", () => {
    const response = middleware(requestFor("/login", { withSession: false }));

    expect(response.headers.get("location")).toBeNull();
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("sends a visitor with a session cookie from /login to the home page", () => {
    const response = middleware(requestFor("/login", { withSession: true }));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(`${ORIGIN}/`);
  });

  it("lets a rejected session reach the expired-login notice instead of looping", () => {
    const response = middleware(requestFor("/login?reason=expired", { withSession: true }));

    expect(response.headers.get("location")).toBeNull();
  });

  it("lets a visitor with a session cookie through to a protected page", () => {
    const response = middleware(requestFor("/users", { withSession: true }));

    expect(response.headers.get("location")).toBeNull();
  });

  it("sends the nonce-based policy on public and authenticated pages", () => {
    for (const [pathname, withSession] of [
      ["/login", false],
      ["/users", true],
    ] as const) {
      const policy = middleware(requestFor(pathname, { withSession })).headers.get(
        "content-security-policy",
      );

      expect(policy).toContain("default-src 'self'");
      expect(policy).toContain("frame-ancestors 'none'");
      expect(policy).toContain("base-uri 'self'");
      expect(policy).toContain("object-src 'none'");
      expect(policy).toContain("form-action 'self'");
      expect(scriptSources(policy)).toMatch(/'nonce-[A-Za-z0-9+/=]+'/);
      expect(scriptSources(policy)).toContain("'strict-dynamic'");
      expect(scriptSources(policy)).not.toContain("'unsafe-inline'");
      expect(scriptSources(policy)).not.toContain("'unsafe-eval'");
    }
  });

  it("hands the same nonce and policy to rendering through the request headers", () => {
    const response = middleware(requestFor("/login", { withSession: false }));
    const policy = response.headers.get("content-security-policy");

    expect(response.headers.get("x-middleware-override-headers")).toContain("x-nonce");
    expect(response.headers.get("x-middleware-request-x-nonce")).toBe(nonceOf(policy));
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(policy);
  });

  it("gives two requests for the same page different nonces", () => {
    const first = middleware(requestFor("/login", { withSession: false }));
    const second = middleware(requestFor("/login", { withSession: false }));

    expect(nonceOf(first.headers.get("content-security-policy"))).not.toBe(
      nonceOf(second.headers.get("content-security-policy")),
    );
  });

  it("sends a visitor whose access cookie lapsed through renewal back to the same page", () => {
    const response = middleware(
      lapsedRequest("/users?page=2", { cookies: ["app_csrf"], secFetchSite: "none" }),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      `${ORIGIN}/api/auth/renew?next=%2Fusers%3Fpage%3D2`,
    );
  });

  it("sends a visitor to /login right after a renewal, from another site, or without a session", () => {
    for (const options of [
      { cookies: ["app_csrf", "app_renewed"], secFetchSite: "same-origin" },
      { cookies: ["app_csrf"], secFetchSite: "cross-site" },
      { cookies: [], secFetchSite: "same-origin" },
    ]) {
      const response = middleware(lapsedRequest("/users", options));

      expect(response.headers.get("location")).toBe(`${ORIGIN}/login`);
    }
  });

  it("hands the page's path and query to rendering for requireUser", () => {
    const response = middleware(requestFor("/users?page=2", { withSession: true }));

    expect(response.headers.get("x-middleware-request-x-app-path")).toBe("/users?page=2");
  });
});
