import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = new Set(["/login"]);

/**
 * A cheap, cookie-presence-only redirect. This is a UX optimization, not the
 * authorization boundary — middleware can be bypassed
 * (CVE-2025-29927, CVE-2026-64642), so every protected data path still
 * verifies the session server-side through `lib/auth/dal.ts`.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("app_access");

  if (!hasSession && !PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (hasSession && PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
