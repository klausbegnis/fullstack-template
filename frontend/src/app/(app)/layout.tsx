import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { LogoutButton } from "@/features/auth/containers/logout-button";
import { requireUser } from "@/lib/auth/dal";

export interface AppLayoutProps {
  children: ReactNode;
}

/**
 * The layout for every authenticated route. `requireUser()` is the real
 * authorization check — it calls FastAPI's `/auth/me` and redirects to
 * `/login` when there is no session. `middleware.ts` only performs a cheap
 * cookie-presence redirect and must never be relied on alone
 * (CVE-2025-29927).
 */
export default async function AppLayout({ children }: AppLayoutProps) {
  const user = await requireUser();

  return (
    <AppShell productName="Kitchen AI" actions={<LogoutButton />}>
      <p className="mb-4 text-sm text-gray-500">Signed in as {user.name}</p>
      {children}
    </AppShell>
  );
}
