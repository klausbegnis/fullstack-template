import type { ReactNode } from "react";

export interface HeaderProps {
  productName: string;
  actions?: ReactNode;
}

/**
 * The application's semantic `<header>`, rendered on the server. Any
 * interactive content, such as a user menu, is passed in as `actions` from
 * a feature that owns that behaviour.
 */
export function Header({ productName, actions }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
      <span className="text-base font-semibold text-gray-900">{productName}</span>
      {actions}
    </header>
  );
}
