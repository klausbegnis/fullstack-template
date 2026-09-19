import type { ReactNode } from "react";
import { Header } from "@/components/layout/header";
import { Nav } from "@/components/layout/nav";
import { navItems } from "@/components/layout/nav-items";
import { SkipLink } from "@/components/layout/skip-link";

export interface AppShellProps {
  productName: string;
  actions?: ReactNode;
  children: ReactNode;
}

/**
 * The application shell: skip-link, semantic header and navigation, and the
 * `<main>` landmark the skip-link targets. Rendered entirely on the server —
 * code crosses through imports, data crosses through props.
 */
export function AppShell({ productName, actions, children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <SkipLink />
      <Header productName={productName} actions={actions} />
      <div className="flex flex-1">
        <aside className="w-56 border-r border-gray-200 p-4">
          <Nav items={navItems} />
        </aside>
        <main id="main-content" className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
