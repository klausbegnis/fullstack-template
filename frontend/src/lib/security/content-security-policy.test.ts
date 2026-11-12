import { describe, expect, it } from "vitest";
import { buildContentSecurityPolicy, createNonce } from "@/lib/security/content-security-policy";

function directive(policy: string, name: string): string | undefined {
  return policy
    .split("; ")
    .find((entry) => entry.startsWith(`${name} `))
    ?.slice(name.length + 1);
}

describe("buildContentSecurityPolicy", () => {
  it("builds the production policy with the nonce and no eval or inline scripts", () => {
    const policy = buildContentSecurityPolicy("n0nce", { development: false });

    expect(policy).toBe(
      "default-src 'self'; " +
        "script-src 'self' 'nonce-n0nce' 'strict-dynamic'; " +
        "style-src 'self' 'unsafe-inline'; " +
        "img-src 'self' data: blob:; " +
        "font-src 'self'; " +
        "media-src 'self'; " +
        "connect-src 'self'; " +
        "frame-ancestors 'none'; " +
        "base-uri 'self'; " +
        "object-src 'none'; " +
        "form-action 'self'",
    );
  });

  it("allows eval in scripts only for development", () => {
    const development = buildContentSecurityPolicy("n0nce", { development: true });
    const production = buildContentSecurityPolicy("n0nce", { development: false });

    expect(directive(development, "script-src")).toBe(
      "'self' 'nonce-n0nce' 'strict-dynamic' 'unsafe-eval'",
    );
    expect(directive(production, "script-src")).not.toContain("'unsafe-eval'");
    expect(directive(development, "script-src")).not.toContain("'unsafe-inline'");
  });
});

describe("createNonce", () => {
  it("returns a base64 value from 16 random bytes", () => {
    const nonce = createNonce();

    expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
  });

  it("returns a different value each call", () => {
    expect(createNonce()).not.toBe(createNonce());
  });
});
