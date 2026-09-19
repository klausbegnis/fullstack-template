import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/errors/api-error";
import { parseApiResponse } from "@/lib/api/parse-response";

describe("parseApiResponse", () => {
  it("unwraps the data field of a success envelope", async () => {
    const response = new Response(
      JSON.stringify({ success: true, message: "ok", data: { id: "a1" } }),
      { status: 200 },
    );
    await expect(parseApiResponse(response)).resolves.toEqual({ id: "a1" });
  });

  it("returns a paginated envelope whole", async () => {
    const body = {
      success: true,
      data: [{ id: "a1" }],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    };
    const response = new Response(JSON.stringify(body), { status: 200 });
    await expect(parseApiResponse(response)).resolves.toEqual(body);
  });

  it("returns a bare body with no envelope, such as /auth/me", async () => {
    const body = { id: "a1", name: "Ada Lovelace", email: "ada@example.com", role: "admin" };
    const response = new Response(JSON.stringify(body), { status: 200 });
    await expect(parseApiResponse(response)).resolves.toEqual(body);
  });

  it("resolves to undefined for a 204 No Content response", async () => {
    const response = new Response(null, { status: 204 });
    await expect(parseApiResponse(response)).resolves.toBeUndefined();
  });

  it("throws an ApiError built from an error envelope", async () => {
    const body = {
      error: {
        code: "validation_error",
        message: "Invalid request data",
        details: { errors: [{ type: "missing", loc: ["body", "name"], msg: "Field required" }] },
      },
      request_id: "req-1",
    };
    const response = new Response(JSON.stringify(body), { status: 422 });

    const error = await parseApiResponse(response).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "validation_error",
      requestId: "req-1",
    });
  });

  it("throws an ApiError for a non-JSON failure response", async () => {
    const response = new Response("", { status: 502, statusText: "Bad Gateway" });

    const error = await parseApiResponse(response).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
  });
});
