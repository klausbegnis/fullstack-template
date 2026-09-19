export interface ApiRequestConfig {
  url: string;
  method: string;
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

export const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export const CSRF_COOKIE_NAME = "app_csrf";

export const CSRF_HEADER_NAME = "X-CSRF-Token";

/**
 * Appends query params to a URL, dropping any `undefined` or `null` value.
 */
export function buildRequestUrl(url: string, params?: Record<string, unknown>): string {
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.append(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

/**
 * Builds the shared request headers for an API call: JSON `Accept`, a JSON
 * `Content-Type` when a body is present, and any caller-supplied headers.
 */
export function buildRequestHeaders(config: ApiRequestConfig): Headers {
  const headers = new Headers(config.headers);
  headers.set("Accept", "application/json");
  if (config.data !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}
