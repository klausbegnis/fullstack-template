import type { ReactNode } from "react";

export interface HeaderProps {
  productName: string;
  accountMenu?: ReactNode;
  menuButton?: ReactNode;
}

/**
 * The application's semantic `<header>`: one compact row with the product name, the signed-in
 * user's `accountMenu` and the phone-only `menuButton`. Interactive content arrives as slots from
 * the shell and the layout, which own that behaviour.
 */
export function Header({ productName, accountMenu, menuButton }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-16 items-center justify-between gap-3 border-b border-gray-200 bg-white px-4 sm:px-6">
      <span className="truncate text-base font-semibold text-gray-900">{productName}</span>
      <div className="flex flex-none items-center gap-3">
        {accountMenu}
        {menuButton}
      </div>
    </header>
  );
}
