/** The session cookie whose absence sends a protected page through renewal. */
export const ACCESS_COOKIE_NAME = "app_access";

/** The refresh cookie, scoped by the API to `REFRESH_COOKIE_PATH`. */
export const REFRESH_COOKIE_NAME = "app_refresh";

/** The only path the browser sends the refresh cookie to. */
export const REFRESH_COOKIE_PATH = "/api/auth";

/**
 * The short-lived loop guard the renew handler sets: while it is present a
 * page that still has no session goes to `/login` instead of renewing again.
 */
export const RENEWED_COOKIE_NAME = "app_renewed";

/** How long the loop guard lives. */
export const RENEWED_COOKIE_MAX_AGE_SECONDS = 10;

/**
 * The Next Route Handler that renews a session during a navigation. It sits
 * under `/api/auth` so the browser sends it the path-scoped refresh cookie.
 */
export const RENEW_PATH = "/api/auth/renew";

/** The request header the middleware sets with the page's path and query for `requireUser()`. */
export const RETURN_PATH_HEADER = "x-app-path";

const RENEWABLE_FETCH_SITES = new Set(["same-origin", "none"]);

/**
 * False when a request's `Sec-Fetch-Site` says it came from another site;
 * only same-origin and address-bar navigations may rotate the session.
 * Browsers send no fetch metadata to a plain-HTTP origin other than
 * localhost, so a missing header is allowed here and the renew handler checks
 * the `Referer` instead.
 */
export function canRenewFrom(secFetchSite: string | null | undefined): boolean {
  return secFetchSite == null || RENEWABLE_FETCH_SITES.has(secFetchSite);
}

/** The inputs that decide whether a page without a valid access token may try renewing. */
export interface RenewalSignals {
  hasCsrfCookie: boolean;
  hasRenewedCookie: boolean;
  secFetchSite: string | null | undefined;
}

/**
 * True when a navigation that lost its access token should pass through the
 * renew handler: the visitor still holds a session (`app_csrf`), no renewal
 * just happened (`app_renewed`), and the navigation is same-origin.
 */
export function shouldRenew({
  hasCsrfCookie,
  hasRenewedCookie,
  secFetchSite,
}: RenewalSignals): boolean {
  return hasCsrfCookie && !hasRenewedCookie && canRenewFrom(secFetchSite);
}

/** Builds the renew URL that lands back on `returnPath` once the session is renewed. */
export function renewPathReturningTo(returnPath: string): string {
  return `${RENEW_PATH}?next=${encodeURIComponent(returnPath)}`;
}
