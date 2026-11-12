import "server-only";
import { cookies } from "next/headers";
import { apiServerFetch } from "@/lib/api/server-client";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/api/request-config";
import { ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH } from "@/lib/auth/renewal";

/**
 * Revokes the caller's session through `POST /auth/logout` with the CSRF
 * double-submit header and the browser's `Origin`/`Referer` (forwarded by
 * `apiServerFetch` on every mutation), then clears the three session cookies
 * whether or not the backend call succeeded. Shared by every Server Action
 * that signs the visitor out.
 */
export async function endSession(): Promise<void> {
  const cookieStore = await cookies();
  const csrfToken = cookieStore.get(CSRF_COOKIE_NAME)?.value;

  await apiServerFetch<void>({
    url: "/auth/logout",
    method: "POST",
    headers: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined,
  }).catch(() => undefined);

  cookieStore.delete({ name: ACCESS_COOKIE_NAME, path: "/" });
  cookieStore.delete({ name: REFRESH_COOKIE_NAME, path: REFRESH_COOKIE_PATH });
  cookieStore.delete({ name: CSRF_COOKIE_NAME, path: "/" });
}
