import { describe, expect, it } from "vitest";
import { publicEnv, serverEnv } from "@/lib/env";

describe("env", () => {
  it("parses server env with a default API proxy target", () => {
    expect(serverEnv.API_PROXY_TARGET).toBe("http://localhost:8000");
  });

  it("parses public env with a default API base URL", () => {
    expect(publicEnv.NEXT_PUBLIC_API_BASE_URL).toBe("/api");
  });
});
