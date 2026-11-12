const NONCE_BYTES = 16;

/** The response and request header that carries the page's policy. */
export const CONTENT_SECURITY_POLICY_HEADER = "Content-Security-Policy";

/** The request header the middleware uses to hand the nonce to rendering. */
export const NONCE_HEADER = "x-nonce";

/** Whether the policy is built for `next dev`, which needs `eval` for its overlays. */
export interface ContentSecurityPolicyOptions {
  development: boolean;
}

/**
 * A fresh base64 nonce from 16 random bytes. Uses Web Crypto and `btoa` so it
 * runs unchanged in the Edge and Node middleware runtimes.
 */
export function createNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(NONCE_BYTES));
  return btoa(String.fromCharCode(...bytes));
}

function scriptSources(nonce: string, { development }: ContentSecurityPolicyOptions): string {
  const sources = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"];
  return (development ? [...sources, "'unsafe-eval'"] : sources).join(" ");
}

/**
 * The page policy: same-origin everything, scripts only through the
 * per-request nonce (and what those scripts load, via `'strict-dynamic'`),
 * inline styles allowed for React style attributes, `data:` and `blob:`
 * images for local previews, and no framing, plugins, base rewrites or
 * cross-origin form posts. `'unsafe-eval'` is added only for `next dev`.
 */
export function buildContentSecurityPolicy(
  nonce: string,
  options: ContentSecurityPolicyOptions,
): string {
  return [
    "default-src 'self'",
    `script-src ${scriptSources(nonce, options)}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "media-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
    "form-action 'self'",
  ].join("; ");
}
