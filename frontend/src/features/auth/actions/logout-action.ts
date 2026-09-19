"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { apiServerFetch } from "@/lib/api/server-client";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/api/request-config";

async function callBackendLogout(csrfToken: string | undefined): Promise<void> {
  await apiServerFetch<void>({
    url: "/auth/logout",
    method: "POST",
    headers: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined,
  });
}

/**
 * Calls `POST /auth/logout` with the CSRF double-submit header read from the
 * readable `app_csrf` cookie, then clears the three session cookies
 * regardless of whether the backend call succeeded, and redirects to
 * `/login`. The other of this template's two Server Actions — see
 * `loginAction` for why mutations otherwise go through `useMutation`.
 */
export async function logoutAction(): Promise<void> {
  const cookieStore = await cookies();
  const csrfToken = cookieStore.get(CSRF_COOKIE_NAME)?.value;

  await callBackendLogout(csrfToken).catch(() => undefined);

  cookieStore.delete({ name: "app_access", path: "/" });
  cookieStore.delete({ name: "app_refresh", path: "/api/auth" });
  cookieStore.delete({ name: CSRF_COOKIE_NAME, path: "/" });

  redirect("/login");
}
