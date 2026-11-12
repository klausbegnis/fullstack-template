"use client";

import { publicEnv } from "@/lib/env";
import { parseApiResponse } from "@/lib/api/parse-response";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, MUTATING_METHODS } from "@/lib/api/request-config";
import { refreshSession } from "@/lib/auth/refresh-session";

/** Reads one cookie the browser exposes to scripts, such as the readable `app_csrf` token. */
export function readBrowserCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}

const SESSION_ENDPOINTS = new Set(["/auth/refresh", "/auth/login", "/auth/logout"]);
const UNAUTHORIZED_STATUS = 401;

function retriesAfterRefresh(url: string): boolean {
  const [path = url] = url.split("?");
  return !SESSION_ENDPOINTS.has(path);
}

function send(url: string, options: RequestInit): Promise<Response> {
  const method = (options.method ?? "GET").toString().toUpperCase();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readBrowserCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  return fetch(`${publicEnv.NEXT_PUBLIC_API_BASE_URL}${url}`, {
    ...options,
    headers,
    credentials: "include",
  });
}

/**
 * The mutator orval's fetch client injects into every generated browser
 * call, invoked as `apiMutator(url, requestInit)`. It resolves the URL
 * against the `/api` rewrite, sends `credentials: "include"` so the httpOnly
 * session cookies ride along, attaches the CSRF header from the readable
 * `app_csrf` cookie on mutating requests, and unwraps the backend envelope —
 * throwing `ApiError` on any failure. A 401 from anything but
 * `/auth/refresh`, `/auth/login` or `/auth/logout` renews the session through
 * `refreshSession()` and retries the request once with freshly built headers,
 * so a retried mutation carries the rotated CSRF token; a session that cannot
 * be renewed surfaces the original 401. Use `apiServerFetch` from
 * `server-client.ts` instead when calling the API from a Server Component,
 * a Server Action, or a Route Handler.
 */
export async function apiMutator<TData>(url: string, options: RequestInit = {}): Promise<TData> {
  const response = await send(url, options);
  if (response.status === UNAUTHORIZED_STATUS && retriesAfterRefresh(url)) {
    const outcome = await refreshSession();
    if (outcome.status === "refreshed") {
      return parseApiResponse<TData>(await send(url, options));
    }
  }
  return parseApiResponse<TData>(response);
}

export default apiMutator;
