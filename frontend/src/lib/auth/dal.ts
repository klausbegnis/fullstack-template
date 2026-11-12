import "server-only";
import { cache } from "react";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { apiServerFetch } from "@/lib/api/server-client";
import { CSRF_COOKIE_NAME } from "@/lib/api/request-config";
import { ApiError } from "@/lib/errors/api-error";
import {
  ACCESS_COOKIE_NAME,
  RENEWED_COOKIE_NAME,
  RETURN_PATH_HEADER,
  renewPathReturningTo,
  shouldRenew,
} from "@/lib/auth/renewal";
import { expiredLoginPath, safeReturnPath } from "@/lib/auth/return-path";

export type AuthUserRole = "admin" | "member";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: AuthUserRole;
}

/**
 * Reads the current session from FastAPI, forwarding the incoming request's
 * cookies. This is the real authorization check for this template — every
 * protected data path must call it (directly or through `requireUser`)
 * rather than trusting `middleware.ts`, which only performs a cheap
 * cookie-presence redirect and must never be the sole guard
 * (CVE-2025-29927). Wrapped in React's `cache()` so a single render pass
 * verifies the session once no matter how many components ask.
 */
export const getCurrentUser = cache(async (): Promise<AuthUser | null> => {
  try {
    return await apiServerFetch<AuthUser>({ url: "/auth/me", method: "GET" });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
});

async function signedOutDestination(): Promise<string> {
  const [cookieStore, incoming] = await Promise.all([cookies(), headers()]);
  const renew = shouldRenew({
    hasCsrfCookie: cookieStore.has(CSRF_COOKIE_NAME),
    hasRenewedCookie: cookieStore.has(RENEWED_COOKIE_NAME),
    secFetchSite: incoming.get("sec-fetch-site"),
  });
  const returnPath = safeReturnPath(incoming.get(RETURN_PATH_HEADER)) ?? "/";
  if (renew) return renewPathReturningTo(returnPath);
  return cookieStore.has(ACCESS_COOKIE_NAME) ? expiredLoginPath(returnPath) : "/login";
}

/**
 * Reads the current session and redirects when there is none: through the
 * `/api/auth/renew` Route Handler back to the current page (the path the
 * middleware put in `x-app-path`) while the visitor still holds a session
 * cookie and no renewal just happened, otherwise to `/login`, marked
 * `reason=expired` while a rejected access cookie is still present so the
 * middleware does not bounce the visitor straight back.
 * Call this from the layout of any route group that requires a signed-in
 * user, and from any Server Action that performs a sensitive mutation.
 */
export async function requireUser(): Promise<AuthUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect(await signedOutDestination());
  }
  return user;
}
