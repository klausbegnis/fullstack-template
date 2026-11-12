"use server";

import { redirect } from "next/navigation";
import { endSession } from "@/lib/auth/end-session";

/**
 * Revokes the session and clears the session cookies through `endSession`,
 * then redirects to `/login`. The other of this template's two Server
 * Actions — see `loginAction` for why mutations otherwise go through
 * `useMutation`.
 */
export async function logoutAction(): Promise<void> {
  await endSession();
  redirect("/login");
}
