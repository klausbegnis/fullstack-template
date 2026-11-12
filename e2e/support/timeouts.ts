/**
 * Per-test budget for every project: about three times the slowest test on an idle laptop, so a
 * loaded CI runner still fits while a hung page fails well before Playwright's default.
 */
export const TEST_TIMEOUT_MS = 40_000;

/**
 * Budget for one web-first assertion. A missing element still fails well inside the test budget.
 */
export const EXPECT_TIMEOUT_MS = 15_000;
