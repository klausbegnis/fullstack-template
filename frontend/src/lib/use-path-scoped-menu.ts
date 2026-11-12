"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

/** Open state of a menu and the controls that flip or close it. */
export interface PathScopedMenu {
  expanded: boolean;
  toggle: () => void;
  close: () => void;
}

/**
 * Open state of a navigation menu that belongs to the scope it was opened on: the path, plus any
 * context the path alone does not carry. Any change of scope closes it, and it stays closed until
 * it is toggled again, even when the user comes back to that scope through a link or the browser
 * history.
 */
export function usePathScopedMenu(scope: string | null): PathScopedMenu {
  const [menu, setMenu] = useState({ scope, expanded: false });
  if (menu.scope !== scope) {
    setMenu({ scope, expanded: false });
  }
  const expanded = menu.scope === scope && menu.expanded;
  return {
    expanded,
    toggle: () => setMenu({ scope, expanded: !expanded }),
    close: () => setMenu({ scope, expanded: false }),
  };
}

/**
 * Path-scoped menu for the current route: it closes on every navigation and, with `context`, on
 * any change of a scope the path alone does not carry.
 */
export function useRouteScopedMenu(context = ""): PathScopedMenu {
  const pathname = usePathname();
  return usePathScopedMenu(`${pathname}#${context}`);
}
