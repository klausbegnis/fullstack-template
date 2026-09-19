import "server-only";
import { cookies } from "next/headers";
import { serverEnv } from "@/lib/env";
import { parseApiResponse } from "@/lib/api/parse-response";
import { buildRequestHeaders, buildRequestUrl } from "@/lib/api/request-config";
import type { ApiRequestConfig } from "@/lib/api/request-config";

/**
 * The server-side counterpart to `mutator.ts`, used from Server Components,
 * Route Handlers and the auth DAL. It talks to FastAPI directly through
 * `API_PROXY_TARGET` rather than through the `/api` rewrite, forwards the
 * incoming request's cookies so the backend sees the caller's session, and
 * unwraps the envelope exactly like the browser mutator.
 */
export async function apiServerFetch<TData>(config: ApiRequestConfig): Promise<TData> {
  const method = config.method.toUpperCase();
  const headers = buildRequestHeaders(config);

  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  if (cookieHeader) headers.set("Cookie", cookieHeader);

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
