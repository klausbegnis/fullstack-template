"use client";

import { publicEnv } from "@/lib/env";
import { parseApiResponse } from "@/lib/api/parse-response";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, MUTATING_METHODS } from "@/lib/api/request-config";

function readBrowserCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}

/**
 * The mutator orval's fetch client injects into every generated browser
 * call, invoked as `apiMutator(url, requestInit)`. It resolves the URL
 * against the `/api` rewrite, sends `credentials: "include"` so the httpOnly
 * session cookies ride along, attaches the CSRF header from the readable
 * `app_csrf` cookie on mutating requests, and unwraps the backend envelope —
 * throwing `ApiError` on any failure. Use `apiServerFetch` from
 * `server-client.ts` instead when calling the API from a Server Component,
 * a Server Action, or a Route Handler.
 */
export async function apiMutator<TData>(url: string, options: RequestInit = {}): Promise<TData> {
  const method = (options.method ?? "GET").toString().toUpperCase();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readBrowserCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  const response = await fetch(`${publicEnv.NEXT_PUBLIC_API_BASE_URL}${url}`, {
    ...options,
    headers,
    credentials: "include",
  });

  return parseApiResponse<TData>(response);
}

export default apiMutator;
