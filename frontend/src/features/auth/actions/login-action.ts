"use server";

import { redirect } from "next/navigation";
import { serverEnv } from "@/lib/env";
import { parseApiResponse } from "@/lib/api/parse-response";
import { forwardedJsonHeaders } from "@/lib/auth/forwarded-headers";
import { safeReturnPath } from "@/lib/auth/return-path";
import { applySetCookieHeaders } from "@/lib/auth/set-cookie";
import { ApiError } from "@/lib/errors/api-error";
import type { LoginValues } from "@/features/auth/model/login-schema";

export interface LoginActionResult {
  status: "error";
  message: string;
}

/**
 * Posts credentials to FastAPI and forwards its `Set-Cookie` headers to the
 * browser, then redirects to `returnTo` when it is a safe same-origin path
 * (see `safeReturnPath`) and to `/` otherwise. This — together with
 * `logoutAction` — is the only place in the template a React 19 Action is
 * used for a mutation: writing the httpOnly session cookie is the one thing
 * only the Next server can do. On failure it returns a result instead of throwing, since a
 * thrown error crossing the Server Action boundary is redacted by Next in
 * production.
 */
export async function loginAction(
  values: LoginValues,
  returnTo?: string | null,
): Promise<LoginActionResult> {
  try {
    const response = await fetch(`${serverEnv.API_PROXY_TARGET}/auth/login`, {
      method: "POST",
      headers: await forwardedJsonHeaders(),
      body: JSON.stringify(values),
      cache: "no-store",
    });
    const setCookieHeaders = response.headers.getSetCookie();
    await parseApiResponse(response);
    await applySetCookieHeaders(setCookieHeaders);
  } catch (error) {
    return {
      status: "error",
      message: error instanceof ApiError ? error.message : "Unable to sign in. Please try again.",
    };
  }

  redirect(safeReturnPath(returnTo) ?? "/");
}
