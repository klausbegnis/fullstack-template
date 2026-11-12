import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";
import { disableZodCodeGeneration } from "@/lib/security/disable-zod-code-generation";

describe("disableZodCodeGeneration", () => {
  afterEach(() => {
    z.config({ jitless: false });
  });

  it("switches zod to its jitless parsers", () => {
    disableZodCodeGeneration();

    expect(z.config().jitless).toBe(true);
  });
});
