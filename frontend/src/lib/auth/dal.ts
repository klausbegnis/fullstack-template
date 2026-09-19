import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { apiServerFetch } from "@/lib/api/server-client";
import { ApiError } from "@/lib/errors/api-error";

export type AuthUserRole = "admin" | "member";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: AuthUserRole;
}

/**
 * Reads the current session from FastAPI, forwarding the incoming request's
 * cookies. This is the real authorization check for this template — every
 * protected data path must call it (directly or through `requireUser`)
 * rather than trusting `middleware.ts`, which only performs a cheap
 * cookie-presence redirect and must never be the sole guard
 * (CVE-2025-29927). Wrapped in React's `cache()` so a single render pass
 * verifies the session once no matter how many components ask.
 */
export const getCurrentUser = cache(async (): Promise<AuthUser | null> => {
  try {
    return await apiServerFetch<AuthUser>({ url: "/auth/me", method: "GET" });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
});

/**
 * Reads the current session and redirects to `/login` when there is none.
 * Call this from the layout of any route group that requires a signed-in
 * user, and from any Server Action that performs a sensitive mutation.
 */
export async function requireUser(): Promise<AuthUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}
