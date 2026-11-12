import "server-only";
import { headers } from "next/headers";
import { NONCE_HEADER } from "@/lib/security/content-security-policy";

/**
 * The nonce the middleware generated for this request. Reading it makes the
 * caller render per request, which is what lets Next.js stamp the nonce from
 * the request's `Content-Security-Policy` onto its own scripts; a statically
 * prerendered page would carry none and be blocked by `'strict-dynamic'`.
 */
export async function readRequestNonce(): Promise<string | null> {
  return (await headers()).get(NONCE_HEADER);
}
