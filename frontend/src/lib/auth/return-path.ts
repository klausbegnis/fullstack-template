const RETURN_PATH_BASE = "http://return-path.invalid";
const MAX_RETURN_PATH_LENGTH = 2048;

/**
 * Returns `value` when it is a same-origin path such as `/users?page=2`,
 * otherwise `null`. Absolute URLs, protocol-relative `//host` and `/\host`
 * forms, control characters and over-long values are all rejected, so a
 * `next` query parameter can never send a visitor to another site after login.
 */
export function safeReturnPath(value: string | null | undefined): string | null {
  if (typeof value !== "string" || value.length === 0 || value.length > MAX_RETURN_PATH_LENGTH) {
    return null;
  }
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return null;
  }
  if (/[\u0000-\u001f\u007f\\]/.test(value)) {
    return null;
  }
  const parsed = new URL(value, RETURN_PATH_BASE);
  if (parsed.origin !== RETURN_PATH_BASE || parsed.pathname.startsWith("//")) {
    return null;
  }
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

/** Builds the login URL that returns to `returnPath` after a successful sign-in. */
export function loginPathReturningTo(returnPath: string): string {
  return `/login?next=${encodeURIComponent(returnPath)}`;
}

/** Builds the login URL for a session that ended on its own, showing the expired notice. */
export function expiredLoginPath(returnPath: string): string {
  return `${loginPathReturningTo(returnPath)}&reason=expired`;
}
