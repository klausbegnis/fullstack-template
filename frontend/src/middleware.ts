import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { serverEnv } from "@/lib/env";
import { CSRF_COOKIE_NAME } from "@/lib/api/request-config";
import {
  ACCESS_COOKIE_NAME,
  RENEWED_COOKIE_NAME,
  RETURN_PATH_HEADER,
  renewPathReturningTo,
  shouldRenew,
} from "@/lib/auth/renewal";
import {
  buildContentSecurityPolicy,
  CONTENT_SECURITY_POLICY_HEADER,
  createNonce,
  NONCE_HEADER,
} from "@/lib/security/content-security-policy";

const PUBLIC_PATHS = new Set(["/login"]);
const POST_LOGIN_PATH = "/";

function pathWithQuery(request: NextRequest): string {
  return `${request.nextUrl.pathname}${request.nextUrl.search}`;
}

function nextWithContentSecurityPolicy(request: NextRequest): NextResponse {
  const nonce = createNonce();
  const policy = buildContentSecurityPolicy(nonce, {
    development: serverEnv.NODE_ENV === "development",
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);
  requestHeaders.set(CONTENT_SECURITY_POLICY_HEADER, policy);
  requestHeaders.set(RETURN_PATH_HEADER, pathWithQuery(request));

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(CONTENT_SECURITY_POLICY_HEADER, policy);
  return response;
}

function missingSessionPath(request: NextRequest): string {
  const renew = shouldRenew({
    hasCsrfCookie: request.cookies.has(CSRF_COOKIE_NAME),
    hasRenewedCookie: request.cookies.has(RENEWED_COOKIE_NAME),
    secFetchSite: request.headers.get("sec-fetch-site"),
  });
  return renew ? renewPathReturningTo(pathWithQuery(request)) : "/login";
}

/**
 * A cheap, cookie-presence-only redirect. This is a UX optimization, not the
 * authorization boundary — middleware can be bypassed
 * (CVE-2025-29927, CVE-2026-64642), so every protected data path still
 * verifies the session server-side through `lib/auth/dal.ts`. A visitor whose
 * access cookie lapsed but who still holds a session (`app_csrf`) goes
 * through the `/api/auth/renew` Route Handler and back to the same path and
 * query, unless a renewal just happened (`app_renewed`) or the navigation
 * came from another site, which go to `/login`.
 *
 * Every page it lets through also gets a fresh nonce and the nonce-based
 * `Content-Security-Policy`, on the response and on the request headers the
 * render reads, so Next.js stamps that nonce on its own scripts, and the
 * page's path and query in `x-app-path` for `requireUser()`.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(ACCESS_COOKIE_NAME);

  if (!hasSession && !PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL(missingSessionPath(request), request.url));
  }

  if (hasSession && PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL(POST_LOGIN_PATH, request.url));
  }

  return nextWithContentSecurityPolicy(request);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
