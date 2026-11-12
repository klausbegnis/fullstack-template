"use client";

import { usePathname } from "next/navigation";
import { useRef, type ReactNode } from "react";
import { Header } from "@/components/layout/header";
import { Nav } from "@/components/layout/nav";
import { activeNavHref, phoneTabItems, type NavItem } from "@/components/layout/nav-items";
import { PhoneTabBar } from "@/components/layout/phone-tab-bar";
import { SkipLink } from "@/components/layout/skip-link";
import { useDismissiblePanel } from "@/components/ui/use-dismissible-panel";
import { cn } from "@/lib/cn";
import { useRouteScopedMenu } from "@/lib/use-path-scoped-menu";

const APP_MENU_ID = "app-menu";

export interface AppShellProps {
  productName: string;
  items: readonly NavItem[];
  accountMenu?: ReactNode;
  children: ReactNode;
}

const SIDEBAR_LAYOUT = {
  root: "lg:flex",
  aside: "lg:sticky lg:top-0 lg:block lg:h-screen lg:w-60 lg:flex-none lg:border-r",
  drawerOpen:
    "max-lg:fixed max-lg:inset-x-0 max-lg:top-16 max-lg:bottom-0 max-lg:z-50 max-lg:overflow-y-auto",
  drawerClosed: "max-lg:hidden",
  menuButton: "lg:hidden",
  content: "",
};

const TAB_BAR_LAYOUT = {
  root: "md:flex",
  aside: "md:sticky md:top-0 md:block md:h-screen md:w-60 md:flex-none md:border-r",
  drawerOpen:
    "max-md:fixed max-md:inset-x-0 max-md:top-16 max-md:bottom-tab-bar-clearance max-md:z-50 max-md:overflow-y-auto",
  drawerClosed: "max-md:hidden",
  menuButton: "md:hidden",
  content: "max-md:pb-tab-bar-clearance",
};

/**
 * The responsive application frame: skip link, a one-row header with the product name and the
 * `accountMenu` slot, the primary navigation and the `<main>` landmark the skip link targets.
 * From the desktop breakpoint up the navigation is a sidebar; below it, it becomes a menu under
 * the header that opens from the header's menu button and closes on Escape, a tap outside it and
 * every navigation. When an item carries a `phoneTab` label, phones also get a bottom tab bar and
 * the sidebar starts at the tablet breakpoint instead. The current entry is derived from the
 * pathname.
 */
export function AppShell({ productName, items, accountMenu, children }: AppShellProps) {
  const tabs = phoneTabItems(items);
  const layout = tabs.length === 0 ? SIDEBAR_LAYOUT : TAB_BAR_LAYOUT;
  const activeHref = activeNavHref(items, usePathname());
  const menu = useRouteScopedMenu();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useDismissiblePanel<HTMLElement>(menu.expanded, menu.close, menuButtonRef);

  return (
    <div className={cn("min-h-screen bg-white text-gray-900", layout.root)}>
      <SkipLink />
      <aside
        id={APP_MENU_ID}
        ref={menuRef}
        tabIndex={-1}
        aria-label="Menu"
        className={cn(
          "border-gray-200 bg-white focus:outline-none",
          layout.aside,
          menu.expanded ? layout.drawerOpen : layout.drawerClosed,
        )}
      >
        <div className="h-full p-4">
          <Nav items={items} activeHref={activeHref} />
        </div>
      </aside>
      <div className={cn("min-w-0 flex-1", layout.content)}>
        <Header
          productName={productName}
          accountMenu={accountMenu}
          menuButton={
            <button
              ref={menuButtonRef}
              type="button"
              aria-controls={APP_MENU_ID}
              aria-expanded={menu.expanded}
              onClick={menu.toggle}
              className={cn(
                "min-h-11 rounded-lg border border-gray-200 px-3 text-sm font-semibold text-gray-900 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                layout.menuButton,
              )}
            >
              {menu.expanded ? "Close menu" : "Open menu"}
            </button>
          }
        />
        <main id="main-content" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10">
          {children}
        </main>
      </div>
      {tabs.length === 0 ? null : <PhoneTabBar tabs={tabs} activeHref={activeHref} />}
    </div>
  );
}
