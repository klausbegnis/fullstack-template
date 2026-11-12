import { z } from "zod";

/**
 * Stops zod from compiling object parsers with `new Function`. The page
 * policy has no `'unsafe-eval'`, and zod's eval probe, though it catches the
 * refusal, still fires a `securitypolicyviolation` on every page load. Must run
 * before any client module builds a schema, which is why
 * `instrumentation-client.ts` calls it.
 */
export function disableZodCodeGeneration(): void {
  z.config({ jitless: true });
}
