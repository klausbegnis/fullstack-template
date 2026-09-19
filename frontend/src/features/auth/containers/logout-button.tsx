import { logoutAction } from "@/features/auth/actions/logout-action";
import { Button } from "@/components/ui/button";

/**
 * A logout control wired straight to the `logoutAction` Server Action
 * through the form's own `action` prop. It needs no `'use client'` — a
 * `<form action={serverAction}>` runs without client-side JavaScript.
 */
export function LogoutButton() {
  return (
    <form action={logoutAction}>
      <Button type="submit" variant="secondary">
        Log out
      </Button>
    </form>
  );
}
