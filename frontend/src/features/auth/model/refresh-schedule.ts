/** How long before the access token expires a refresh is due: two minutes. */
export const REFRESH_LEAD_MS = 120_000;

/** The widest random spread around the due time, so tabs do not refresh in lockstep. */
export const REFRESH_JITTER_MS = 15_000;

/** The shortest wait before a scheduled refresh, even for a token already past expiry. */
export const MIN_REFRESH_DELAY_MS = 1_000;

/** How long to wait before trying again after the API could not be reached. */
export const REFRESH_RETRY_DELAY_MS = 30_000;

const LEAD_SHARE_OF_REMAINING = 2;
const JITTER_SHARE_OF_REMAINING = 10;

/**
 * Milliseconds to wait before refreshing an access token that expires at
 * `expiresAtMs`. The lead is two minutes, or half the remaining lifetime when
 * that is shorter, so a short-lived token is refreshed halfway instead of in a
 * tight loop; the jitter is ±15 s, or ±10 % of the remaining lifetime. `random`
 * returns a value in [0, 1), like `Math.random`. An expiry that is not a finite
 * number waits the retry delay instead of firing at once.
 */
export function refreshDelayMs(
  expiresAtMs: number,
  nowMs: number,
  random: () => number = Math.random,
): number {
  if (!Number.isFinite(expiresAtMs)) return REFRESH_RETRY_DELAY_MS;
  const remaining = expiresAtMs - nowMs;
  if (remaining <= 0) return MIN_REFRESH_DELAY_MS;
  const lead = Math.min(REFRESH_LEAD_MS, remaining / LEAD_SHARE_OF_REMAINING);
  const jitterSpan = Math.min(REFRESH_JITTER_MS, remaining / JITTER_SHARE_OF_REMAINING);
  const jitter = (random() * 2 - 1) * jitterSpan;
  return Math.max(MIN_REFRESH_DELAY_MS, Math.round(remaining - lead + jitter));
}

/**
 * True when the access token is within the two-minute lead of its expiry or
 * already past it, so a tab coming back to the foreground refreshes at once.
 */
export function isNearExpiry(expiresAtMs: number, nowMs: number): boolean {
  return expiresAtMs - nowMs <= REFRESH_LEAD_MS;
}
