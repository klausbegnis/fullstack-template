import { cn } from "@/lib/cn";
import type { NavItem } from "@/components/layout/nav-items";

export interface NavIconProps {
  item: NavItem;
  className?: string;
}

/** Draws one navigation entry's glyph, hidden from assistive technology beside its label. */
export function NavIcon({ item, className }: NavIconProps) {
  return (
    <span
      className={cn("grid size-5 flex-none place-items-center text-base", className)}
      aria-hidden="true"
    >
      {item.icon}
    </span>
  );
}
