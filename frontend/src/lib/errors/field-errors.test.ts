import { describe, expect, it, vi } from "vitest";
import { applyFieldErrors } from "@/lib/errors/field-errors";
import { ApiError } from "@/lib/errors/api-error";

describe("applyFieldErrors", () => {
  it("sets a field error for each validation issue and returns the message", () => {
    const setError = vi.fn();
    const error = new ApiError({
      status: 422,
      code: "validation_error",
      message: "Invalid request data",
      details: { errors: [{ type: "missing", loc: ["body", "email"], msg: "Field required" }] },
      requestId: "req-1",
    });

    const message = applyFieldErrors(error, setError);

    expect(setError).toHaveBeenCalledWith("email", { type: "server", message: "Field required" });
    expect(message).toBe("Invalid request data");
  });

  it("ignores a details bag with no recognizable validation issues", () => {
    const setError = vi.fn();
    const error = new ApiError({
      status: 409,
      code: "conflict",
      message: "Email already in use",
      details: null,
      requestId: null,
    });

    const message = applyFieldErrors(error, setError);

    expect(setError).not.toHaveBeenCalled();
    expect(message).toBe("Email already in use");
  });

  it("returns a generic message for a non-ApiError", () => {
    const setError = vi.fn();
    const message = applyFieldErrors(new Error("boom"), setError);

    expect(setError).not.toHaveBeenCalled();
    expect(message).toBe("Something went wrong. Please try again.");
  });
});
