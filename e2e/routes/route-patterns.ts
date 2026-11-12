import path from "node:path";

const ROUTE_GROUP = /^\(.+\)$/;
const DYNAMIC_SEGMENT = /\\\[[^\]]+\\\]/g;

/** Turns a `page.tsx` path relative to `frontend/src/app` into its URL pattern, route groups removed. */
export function pagePathToPattern(relativePagePath: string): string {
  const segments = path
    .dirname(relativePagePath)
    .split(path.sep)
    .filter((segment) => segment !== "." && !ROUTE_GROUP.test(segment));
  return `/${segments.join("/")}`;
}

/** Matches a concrete pathname against a pattern whose `[param]` segments accept any value. */
export function patternToRegExp(pattern: string): RegExp {
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(DYNAMIC_SEGMENT, "[^/]+");
  return new RegExp(`^${escaped}/?$`);
}

/** Whether the pathname of `url` belongs to `pattern`. */
export function urlMatchesPattern(url: string, pattern: string): boolean {
  return patternToRegExp(pattern).test(new URL(url).pathname);
}
