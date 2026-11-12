import Link from "next/link";
import { cn } from "@/lib/cn";
import { NavIcon } from "@/components/layout/nav-icon";
import type { PhoneTabItem } from "@/components/layout/nav-items";

export interface PhoneTabBarProps {
  tabs: readonly PhoneTabItem[];
  activeHref: string | null;
}

/**
 * The phone's bottom tab bar: one tab per destination with its short label, the current one
 * marked with a pill behind its icon. It is hidden from the tablet breakpoint up, where the
 * sidebar lists the same destinations.
 */
export function PhoneTabBar({ tabs, activeHref }: PhoneTabBarProps) {
  return (
    <nav
      aria-label="Tabs"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="grid auto-cols-fr grid-flow-col px-1">
        {tabs.map((tab) => {
          const active = tab.href === activeHref;
          return (
            <li key={tab.href} className="min-w-0">
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-tab-bar min-w-0 flex-col items-center justify-center gap-1 rounded-lg text-[0.6875rem] font-semibold focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand",
                  active ? "text-gray-900" : "text-gray-500 hover:text-gray-900",
                )}
              >
                <span
                  className={cn(
                    "flex h-7 items-center justify-center rounded-full px-3.5",
                    active && "bg-gray-100",
                  )}
                >
                  <NavIcon item={tab} />
                </span>
                <span className="max-w-full truncate">{tab.phoneTab}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
