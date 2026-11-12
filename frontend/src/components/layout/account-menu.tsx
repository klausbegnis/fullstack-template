"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useDismissiblePanel } from "@/components/ui/use-dismissible-panel";
import { initialsOf } from "@/lib/initials";

const MENU_ITEM_SELECTOR = '[role="menuitem"]';

export interface AccountMenuProps {
  userName: string;
  userEmail: string;
  children: ReactNode;
}

function menuItems(menu: HTMLElement | null): HTMLElement[] {
  return menu ? Array.from(menu.querySelectorAll<HTMLElement>(MENU_ITEM_SELECTOR)) : [];
}

function nextIndex(key: string, current: number, count: number): number | null {
  if (key === "ArrowDown") return (current + 1) % count;
  if (key === "ArrowUp") return (current - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

/**
 * The signed-in user's account menu: a round button with their initials, named "Account of
 * <name>", that opens their name and email and then the account items passed as `children`, each
 * rendered by the caller as a `role="menuitem"` with `tabIndex={-1}` (the logout control, for
 * instance). Opening focuses the first item, the arrow keys, Home and End move between items, and
 * Escape, a pointer outside or focus leaving the menu close it, giving focus back to the button.
 */
export function AccountMenu({ userName, userEmail, children }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const close = () => setOpen(false);
  const panelRef = useDismissiblePanel<HTMLDivElement>(open, close, buttonRef);
  const menuId = useId();

  useEffect(() => {
    if (open) menuItems(menuRef.current)[0]?.focus();
  }, [open]);

  function moveFocus(event: KeyboardEvent<HTMLDivElement>) {
    const items = menuItems(menuRef.current);
    const current = items.findIndex((item) => item === document.activeElement);
    const target = nextIndex(event.key, current, items.length);
    if (target === null || items.length === 0) return;
    event.preventDefault();
    items[target]?.focus();
  }

  function closeWhenFocusLeaves(event: FocusEvent<HTMLDivElement>) {
    const next = event.relatedTarget;
    if (!(next instanceof Node)) return;
    if (panelRef.current?.contains(next) || buttonRef.current?.contains(next)) return;
    close();
  }

  return (
    <div className="relative flex-none">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="grid size-11 place-items-center rounded-full bg-gray-900 text-sm font-semibold text-white hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <span aria-hidden="true">{initialsOf(userName)}</span>
        <span className="sr-only">Account of {userName}</span>
      </button>
      {open ? (
        <div
          ref={panelRef}
          tabIndex={-1}
          onBlur={closeWhenFocusLeaves}
          className="fixed top-16 right-4 z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-gray-200 bg-white p-2 shadow-lg focus:outline-none lg:absolute lg:top-full lg:right-0"
        >
          <div className="mb-2 border-b border-gray-200 px-3 pt-2 pb-3">
            <p className="truncate text-sm font-semibold text-gray-900">{userName}</p>
            <p className="truncate text-xs text-gray-500">{userEmail}</p>
          </div>
          <div
            ref={menuRef}
            id={menuId}
            role="menu"
            aria-label={`Account of ${userName}`}
            onKeyDown={moveFocus}
            className="flex flex-col gap-1"
          >
            {children}
          </div>
        </div>
      ) : null}
    </div>
  );
}
