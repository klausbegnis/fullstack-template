import "server-only";
import { cookies } from "next/headers";
import { serverEnv } from "@/lib/env";
import { browserOriginHeaders } from "@/lib/auth/forwarded-headers";
import { parseApiResponse } from "@/lib/api/parse-response";
import { MUTATING_METHODS, buildRequestHeaders, buildRequestUrl } from "@/lib/api/request-config";
import type { ApiRequestConfig } from "@/lib/api/request-config";

/**
 * The server-side counterpart to `mutator.ts`, used from Server Components,
 * Route Handlers and the auth DAL. It talks to FastAPI directly through
 * `API_PROXY_TARGET` rather than through the `/api` rewrite, forwards the
 * incoming request's cookies so the backend sees the caller's session, and
 * unwraps the envelope exactly like the browser mutator. On a mutating method
 * it also forwards the incoming browser request's `Origin` and `Referer`, which
 * the API requires before it honours a session cookie on a mutation.
 */
export async function apiServerFetch<TData>(config: ApiRequestConfig): Promise<TData> {
  const method = config.method.toUpperCase();
  const headers = buildRequestHeaders(config);

  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  if (cookieHeader) headers.set("Cookie", cookieHeader);

  if (MUTATING_METHODS.has(method)) {
    for (const [name, value] of Object.entries(await browserOriginHeaders())) {
      headers.set(name, value);
    }
  }

  const url = buildRequestUrl(`${serverEnv.API_PROXY_TARGET}${config.url}`, config.params);

  const response = await fetch(url, {
    method,
    headers,
    signal: config.signal,
    body: config.data === undefined ? undefined : JSON.stringify(config.data),
    cache: "no-store",
  });

  return parseApiResponse<TData>(response);
}

export default apiServerFetch;
