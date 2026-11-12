import "server-only";
import { headers } from "next/headers";

const FORWARDED_FOR_HEADER = "x-forwarded-for";
const REAL_IP_HEADER = "x-real-ip";
const BROWSER_ORIGIN_HEADERS = ["origin", "referer"] as const;

/**
 * JSON request headers for a Server Action calling a public auth endpoint,
 * carrying the client address headers the edge proxy set (`X-Real-IP`,
 * `X-Forwarded-For`), so the API's per-IP limits see the real client rather
 * than this server when `RATE_LIMIT_CLIENT_IP_HEADER` or
 * `RATE_LIMIT_TRUST_FORWARDED` tells it to read them.
 */
export async function forwardedJsonHeaders(): Promise<Record<string, string>> {
  const incoming = await headers();
  const forwarded: Record<string, string> = {};
  for (const name of [REAL_IP_HEADER, FORWARDED_FOR_HEADER]) {
    const value = incoming.get(name);
    if (value) forwarded[name] = value;
  }
  return { "Content-Type": "application/json", Accept: "application/json", ...forwarded };
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
