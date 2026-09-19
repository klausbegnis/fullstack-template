/**
 * Joins class names, dropping any falsy value. A minimal, dependency-free
 * stand-in for `clsx` — this template does not need conflict resolution
 * between Tailwind utility classes.
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
