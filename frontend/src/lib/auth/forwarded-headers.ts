import "server-only";
import { headers } from "next/headers";

const FORWARDED_FOR_HEADER = "x-forwarded-for";
const BROWSER_ORIGIN_HEADERS = ["origin", "referer"] as const;

/**
 * JSON request headers for a Server Action calling a public auth endpoint,
 * carrying the browser's `X-Forwarded-For` so the API's per-IP limits can see
 * the real client when it trusts this proxy.
 */
export async function forwardedJsonHeaders(): Promise<Record<string, string>> {
  const forwardedFor = (await headers()).get(FORWARDED_FOR_HEADER);
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(forwardedFor ? { [FORWARDED_FOR_HEADER]: forwardedFor } : {}),
  };
}

/**
 * The incoming browser request's `Origin` and `Referer`, for a server-side
 * mutation that forwards the visitor's session cookie: the API refuses a
 * cookie-carrying mutation that proves no allowed origin.
 */
export async function browserOriginHeaders(): Promise<Record<string, string>> {
  const incoming = await headers();
  const forwarded: Record<string, string> = {};
  for (const name of BROWSER_ORIGIN_HEADERS) {
    const value = incoming.get(name);
    if (value) forwarded[name] = value;
  }
  return forwarded;
}
