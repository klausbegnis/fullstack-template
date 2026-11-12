import type { ReactNode } from "react";
import { AccountMenu } from "@/components/layout/account-menu";
import { AppShell } from "@/components/layout/app-shell";
import { navItems } from "@/components/layout/nav-items";
import { LogoutButton } from "@/features/auth/containers/logout-button";
import { SessionKeeper } from "@/features/auth/containers/session-keeper";
import { readAccessExpiresAt } from "@/lib/auth/access-expiry";
import { requireUser } from "@/lib/auth/dal";

export interface AppLayoutProps {
  children: ReactNode;
}

/**
 * The layout for every authenticated route. `requireUser()` is the real
 * authorization check — it calls FastAPI's `/auth/me` and, when there is no
 * session, renews it through `/api/auth/renew` or redirects to `/login`.
 * `middleware.ts` only performs a cheap cookie-presence redirect and must
 * never be relied on alone (CVE-2025-29927). The layout also mounts the
 * session keeper with the access token's expiry so the session is renewed
 * before it lapses.
 */
export default async function AppLayout({ children }: AppLayoutProps) {
  const [user, accessExpiresAt] = await Promise.all([requireUser(), readAccessExpiresAt()]);

  return (
    <AppShell
      productName="Fullstack Template"
      items={navItems}
      accountMenu={
        <AccountMenu userName={user.name} userEmail={user.email}>
          <LogoutButton variant="menuitem" />
        </AccountMenu>
      }
    >
      {children}
      <SessionKeeper accessExpiresAt={accessExpiresAt} />
    </AppShell>
  );
}
