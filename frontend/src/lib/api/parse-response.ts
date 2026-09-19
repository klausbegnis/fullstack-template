import { isErrorResponse, isPaginatedResponse, isSuccessResponse } from "@/lib/api/envelope";
import { toApiError, toUnknownApiError } from "@/lib/errors/api-error";

/**
 * Reads a fetch `Response`, parses the backend envelope, and returns the
 * unwrapped payload. A `PaginatedResponse` is returned whole (its metadata
 * matters to the caller), a `SuccessResponse` yields only `data`, a bare
 * body — `/auth/login` and `/auth/me` return the resource with no envelope
 * at all — is returned as-is, a `204 No Content` resolves to `undefined`,
 * and any `ErrorResponse` is rejected as an `ApiError`.
 */
export async function parseApiResponse<TData>(response: Response): Promise<TData> {
  if (response.status === 204) {
    if (!response.ok)
      throw toUnknownApiError(response.status, response.statusText || "Request failed");
    return undefined as TData;
  }

  const text = await response.text();
  const body = text.length > 0 ? (JSON.parse(text) as unknown) : undefined;

  if (body && isErrorResponse(body)) {
    throw toApiError(response.status, body);
  }

  if (!response.ok || body === undefined) {
    throw toUnknownApiError(response.status, response.statusText || "Request failed");
  }

  if (isPaginatedResponse<unknown>(body)) {
    return body as TData;
  }

  if (isSuccessResponse<TData>(body)) {
    return body.data;
  }

  return body as TData;
}
