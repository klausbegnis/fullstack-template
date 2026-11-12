/**
 * One navigation destination: `icon` is a short glyph drawn beside the label, and `phoneTab`,
 * when present, is the short label the phone tab bar lists it under.
 */
export interface NavItem {
  href: string;
  label: string;
  icon: string;
  phoneTab?: string;
}

/** A destination the phone tab bar lists, with its short label. */
export type PhoneTabItem = NavItem & { phoneTab: string };

/** The application's navigation, in display order. */
export const navItems: readonly NavItem[] = [
  { href: "/users", label: "Users", icon: "◎", phoneTab: "Users" },
];

/** Selects the phone tab bar's destinations, in navigation order. */
export function phoneTabItems(items: readonly NavItem[]): PhoneTabItem[] {
  return items.filter((item): item is PhoneTabItem => item.phoneTab !== undefined);
}

/**
 * The `href` of the entry the current path belongs to: the longest one equal to the path or
 * followed in it by a `/`, so `/users/42` marks Users current. `null` when no entry matches.
 */
export function activeNavHref(items: readonly NavItem[], pathname: string | null): string | null {
  if (pathname === null) return null;
  const matches = items
    .map((item) => item.href)
    .filter(
      (href) => pathname === href || pathname.startsWith(href.endsWith("/") ? href : `${href}/`),
    );
  return matches.reduce<string | null>(
    (longest, href) => (longest === null || href.length > longest.length ? href : longest),
    null,
  );
}
