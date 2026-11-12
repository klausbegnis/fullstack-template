import { describe, expect, it } from "vitest";
import { shouldRetryQuery } from "@/lib/query/query-client";
import { ApiError } from "@/lib/errors/api-error";

const apiError = (status: number) =>
  new ApiError({ status, code: "error", message: "failed", details: null, requestId: null });

describe("shouldRetryQuery", () => {
  it("never retries a 4xx answer", () => {
    expect(shouldRetryQuery(0, apiError(403))).toBe(false);
    expect(shouldRetryQuery(0, apiError(404))).toBe(false);
  });

  it("retries a server error or a network failure up to three times", () => {
    expect(shouldRetryQuery(0, apiError(503))).toBe(true);
    expect(shouldRetryQuery(2, new TypeError("fetch failed"))).toBe(true);
    expect(shouldRetryQuery(3, apiError(503))).toBe(false);
  });
});
