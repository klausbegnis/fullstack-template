import { describe, expect, it } from "vitest";
import {
  isErrorResponse,
  isPaginatedResponse,
  isSuccessResponse,
  unwrapEnvelope,
} from "@/lib/api/envelope";

describe("unwrapEnvelope", () => {
  it("returns the data payload from a success envelope", () => {
    const result = unwrapEnvelope({ success: true, message: "ok", data: { id: "a1" } });
    expect(result).toEqual({ id: "a1" });
  });

  it("throws the message from an error envelope", () => {
    expect(() =>
      unwrapEnvelope({
        error: { code: "not_found", message: "Resource not found", details: null },
        request_id: "req-1",
      }),
    ).toThrow("Resource not found");
  });
});

describe("isErrorResponse", () => {
  it("narrows an error envelope", () => {
    expect(
      isErrorResponse({
        error: { code: "not_found", message: "nope", details: null },
        request_id: null,
      }),
    ).toBe(true);
  });

  it("rejects a success envelope", () => {
    expect(isErrorResponse({ success: true, message: "ok", data: {} })).toBe(false);
  });
});

describe("isPaginatedResponse", () => {
  it("recognizes the pagination fields", () => {
    expect(
      isPaginatedResponse({
        success: true,
        data: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      }),
    ).toBe(true);
  });

  it("rejects a plain success envelope", () => {
    expect(isPaginatedResponse({ success: true, message: "ok", data: {} })).toBe(false);
  });
});

describe("isSuccessResponse", () => {
  it("recognizes a plain success envelope", () => {
    expect(isSuccessResponse({ success: true, message: "ok", data: { id: "a1" } })).toBe(true);
  });

  it("rejects a paginated envelope", () => {
    expect(
      isSuccessResponse({
        success: true,
        data: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      }),
    ).toBe(false);
  });

  it("rejects a bare object with no envelope fields", () => {
    expect(isSuccessResponse({ id: "a1", email: "a@example.com" })).toBe(false);
  });
});
