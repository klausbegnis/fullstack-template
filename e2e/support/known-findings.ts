export interface AxeExclusion {
  pattern: string;
  ruleId: string;
  reason: string;
}

export interface OverflowExclusion {
  pattern: string;
  maxViewportWidth: number;
  reason: string;
}

export interface ConsoleAllowance {
  pattern: string;
  message: RegExp;
  reason: string;
}

export interface HeadinglessRoute {
  pattern: string;
  anchor: { role: "button" | "link" | "form"; name: string };
  reason: string;
}

/**
 * Reviewed axe exclusions: one rule id on one route pattern, each with the reason it cannot be
 * fixed in the change that found it. A real violation is fixed in the frontend, not listed here.
 */
export const AXE_EXCLUSIONS: readonly AxeExclusion[] = [];

/** Reviewed horizontal-overflow exclusions: one route pattern at viewports up to a width. */
export const OVERFLOW_EXCLUSIONS: readonly OverflowExclusion[] = [];

/** Reviewed console errors tolerated on one route pattern, each with its reason. */
export const CONSOLE_ALLOWANCES: readonly ConsoleAllowance[] = [];

/** Routes that render no `h1`; the smoke run anchors on another landmark until the heading ships. */
export const HEADINGLESS_ROUTES: readonly HeadinglessRoute[] = [];
