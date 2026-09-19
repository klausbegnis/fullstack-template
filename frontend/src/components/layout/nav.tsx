import Link from "next/link";
import type { NavItem } from "@/components/layout/nav-items";

export interface NavProps {
  items: NavItem[];
}

/**
 * The application's semantic `<nav>`, rendered on the server from a plain
 * list of links. Active-link highlighting, which needs the client-side
 * pathname, belongs in a feature that wraps this with its own client
 * component rather than in this primitive.
 */
export function Nav({ items }: NavProps) {
  return (
    <nav aria-label="Primary">
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
