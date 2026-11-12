import type { NextRequest } from "next/server";
import { serverEnv } from "@/lib/env";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/api/request-config";
import {
  ACCESS_COOKIE_NAME,
  canRenewFrom,
  REFRESH_COOKIE_NAME,
  REFRESH_COOKIE_PATH,
  RENEWED_COOKIE_MAX_AGE_SECONDS,
  RENEWED_COOKIE_NAME,
} from "@/lib/auth/renewal";
import { expiredLoginPath, loginPathReturningTo, safeReturnPath } from "@/lib/auth/return-path";

export const dynamic = "force-dynamic";

const POST_LOGIN_PATH = "/";
const SUPERSEDED_CODE = "refresh_superseded";
const SESSION_ENDED_STATUSES = new Set([401, 403]);
const SEE_OTHER = 303;
const SUPERSEDED_SETTLE_MS = 500;
const FORBIDDEN = 403;

type BackendRefresh =
  | { status: "renewed"; setCookies: string[] }
  | { status: "superseded" }
  | { status: "ended" }
  | { status: "unavailable" };

const RENEWED_COOKIE = `${RENEWED_COOKIE_NAME}=1; Path=/; Max-Age=${RENEWED_COOKIE_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax`;

const CLEARED_SESSION_COOKIES = [
  `${ACCESS_COOKIE_NAME}=; Path=/; Max-Age=0`,
  `${REFRESH_COOKIE_NAME}=; Path=${REFRESH_COOKIE_PATH}; Max-Age=0`,
  `${CSRF_COOKIE_NAME}=; Path=/; Max-Age=0`,
];

function requestOrigin(request: NextRequest): string {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const protocol =
    request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(/:$/, "");
  return host ? `${protocol}://${host}` : request.nextUrl.origin;
}

function comesFromThisOrigin(request: NextRequest): boolean {
  const secFetchSite = request.headers.get("sec-fetch-site");
  if (!canRenewFrom(secFetchSite)) return false;
  if (secFetchSite !== null) return true;
  const referer = request.headers.get("referer");
  if (!referer) return true;
  try {
    return new URL(referer).origin === requestOrigin(request);
  } catch {
    return false;
  }
}

async function errorCode(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json();
    if (typeof body !== "object" || body === null || !("error" in body)) return null;
    const { error } = body;
    if (typeof error !== "object" || error === null || !("code" in error)) return null;
    return typeof error.code === "string" ? error.code : null;
  } catch {
    return null;
  }
}

async function refreshOnBackend(request: NextRequest): Promise<BackendRefresh> {
  const csrfToken = request.cookies.get(CSRF_COOKIE_NAME)?.value;
  if (!csrfToken) return { status: "ended" };
  let response: Response;
  try {
    response = await fetch(`${serverEnv.API_PROXY_TARGET}/auth/refresh`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Cookie: request.headers.get("cookie") ?? "",
        Origin: requestOrigin(request),
        [CSRF_HEADER_NAME]: csrfToken,
      },
      cache: "no-store",
    });
  } catch {
    return { status: "unavailable" };
  }
  if (response.ok) return { status: "renewed", setCookies: response.headers.getSetCookie() };
  if (!SESSION_ENDED_STATUSES.has(response.status)) return { status: "unavailable" };
  return (await errorCode(response)) === SUPERSEDED_CODE
    ? { status: "superseded" }
    : { status: "ended" };
}

function settle(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, SUPERSEDED_SETTLE_MS));
}

function seeOther(location: string, setCookies: readonly string[]): Response {
  const headers = new Headers({ Location: location, "Cache-Control": "no-store" });
  for (const cookie of setCookies) headers.append("Set-Cookie", cookie);
  return new Response(null, { status: SEE_OTHER, headers });
}

/**
 * Renews the session during a page navigation that lost its access token.
 * Only a same-origin or address-bar navigation is served: `Sec-Fetch-Site`
 * must not name another site, and where the browser sends no fetch metadata
 * a `Referer` must be this origin; anything else gets 403. It calls
 * `POST /auth/refresh` with the visitor's cookies, CSRF token and this
 * site's origin as `Origin` (a navigation carries none, and the API refuses
 * a cookie-carrying mutation without an allowed one), forwards the rotated
 * cookies, sets the short-lived `app_renewed` loop guard and returns to the
 * sanitized `next` path. When a sibling request already rotated the token it
 * waits half a second, so the sibling's rotated cookies reach the browser
 * first, and returns there with the guard alone; when the session has ended
 * it clears the three session cookies and sends the visitor to the login
 * page with the expired notice; when the API cannot be reached it goes to the
 * login page and keeps the cookies.
 */
export async function GET(request: NextRequest): Promise<Response> {
  if (!comesFromThisOrigin(request)) {
    return new Response(null, { status: FORBIDDEN });
  }
  const returnPath = safeReturnPath(request.nextUrl.searchParams.get("next")) ?? POST_LOGIN_PATH;
  const refresh = await refreshOnBackend(request);
  switch (refresh.status) {
    case "renewed":
      return seeOther(returnPath, [...refresh.setCookies, RENEWED_COOKIE]);
    case "superseded":
      await settle();
      return seeOther(returnPath, [RENEWED_COOKIE]);
    case "ended":
      return seeOther(expiredLoginPath(returnPath), CLEARED_SESSION_COOKIES);
    case "unavailable":
      return seeOther(loginPathReturningTo(returnPath), []);
  }
}
