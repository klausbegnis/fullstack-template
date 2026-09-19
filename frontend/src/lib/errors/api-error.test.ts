import { describe, expect, it } from "vitest";
import { toApiError, toUnknownApiError } from "@/lib/errors/api-error";

describe("toApiError", () => {
  it("maps an ErrorResponse envelope to an ApiError", () => {
    const error = toApiError(404, {
      error: { code: "not_found", message: "User not found", details: null },
      request_id: "req-1",
    });

    expect(error.status).toBe(404);
    expect(error.code).toBe("not_found");
    expect(error.message).toBe("User not found");
    expect(error.requestId).toBe("req-1");
  });

  it("carries the details bag through unchanged", () => {
    const error = toApiError(422, {
      error: {
        code: "validation_error",
        message: "Invalid request data",
        details: { errors: [{ type: "missing", loc: ["body", "email"], msg: "Field required" }] },
      },
      request_id: null,
    });

    expect(error.details).toEqual({
      errors: [{ type: "missing", loc: ["body", "email"], msg: "Field required" }],
    });
  });
});

describe("toUnknownApiError", () => {
  it("builds a fallback ApiError with no details", () => {
    const error = toUnknownApiError(500, "Internal Server Error");

    expect(error.status).toBe(500);
    expect(error.code).toBe("unknown_error");
    expect(error.details).toBeNull();
  });
});
