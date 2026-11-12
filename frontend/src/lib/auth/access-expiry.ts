import "server-only";
import { cookies } from "next/headers";
import { ACCESS_COOKIE_NAME } from "@/lib/auth/renewal";

const MILLISECONDS_PER_SECOND = 1000;

/**
 * Reads the `exp` claim of an access token as epoch milliseconds, or `null`
 * when the value is not a JWT with a numeric `exp`. The signature is NOT
 * verified: the result only schedules the next refresh and never grants
 * access.
 */
export function accessTokenExpiresAt(token: string | null | undefined): number | null {
  const payload = token?.split(".")[1];
  if (!payload) return null;
  try {
    const claims: unknown = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (typeof claims !== "object" || claims === null || !("exp" in claims)) return null;
    const { exp } = claims;
    return typeof exp === "number" && Number.isFinite(exp) ? exp * MILLISECONDS_PER_SECOND : null;
  } catch {
    return null;
  }
}

/** When the incoming request's `app_access` cookie expires, as epoch milliseconds. */
export async function readAccessExpiresAt(): Promise<number | null> {
  const cookieStore = await cookies();
  return accessTokenExpiresAt(cookieStore.get(ACCESS_COOKIE_NAME)?.value);
}
