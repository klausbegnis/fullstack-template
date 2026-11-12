import Link from "next/link";
import { cn } from "@/lib/cn";
import { NavIcon } from "@/components/layout/nav-icon";
import type { NavItem } from "@/components/layout/nav-items";

export interface NavProps {
  items: readonly NavItem[];
  activeHref: string | null;
}

/**
 * The application's primary `<nav>`, rendered from a plain list of links: the sidebar on larger
 * screens and the content of the phone menu. The entry whose `href` is `activeHref` is marked as
 * the current page; the caller derives it from the pathname.
 */
export function Nav({ items, activeHref }: NavProps) {
  return (
    <nav aria-label="Primary">
      <ul className="flex flex-col gap-1">
        {items.map((item) => {
          const active = item.href === activeHref;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                  active ? "bg-gray-100 text-gray-900" : "text-gray-700 hover:bg-gray-100",
                )}
              >
                <NavIcon item={item} />
                <span className="min-w-0 break-words">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
