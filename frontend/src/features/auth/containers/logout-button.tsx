import { logoutAction } from "@/features/auth/actions/logout-action";
import { Button } from "@/components/ui/button";

export interface LogoutButtonProps {
  variant?: "button" | "menuitem";
}

/**
 * A logout control wired straight to the `logoutAction` Server Action
 * through the form's own `action` prop. It needs no `'use client'` — a
 * `<form action={serverAction}>` runs without client-side JavaScript. The
 * `menuitem` variant renders it as an item of a `role="menu"`, such as the
 * account menu, which moves focus between items itself.
 */
export function LogoutButton({ variant = "button" }: LogoutButtonProps) {
  return (
    <form action={logoutAction}>
      {variant === "menuitem" ? (
        <button
          type="submit"
          role="menuitem"
          tabIndex={-1}
          className="flex min-h-11 w-full items-center rounded-lg px-3 text-left text-sm font-semibold text-gray-900 hover:bg-gray-100 focus-visible:bg-gray-100 focus-visible:outline-none"
        >
          Log out
        </button>
      ) : (
        <Button type="submit" variant="secondary">
          Log out
        </Button>
      )}
    </form>
  );
}
