import type { ErrorResponse } from "@/lib/api/envelope";

export interface ApiErrorOptions {
  status: number;
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  requestId: string | null;
}

/**
 * Typed error carrying the HTTP status, the backend's stable `error.code`, a
 * human-readable message, and the raw `error.details` bag. Every mutating
 * call in this template rejects with an `ApiError` rather than a bare
 * `Error` or the raw `Response`.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | null;
  readonly requestId: string | null;

  constructor(options: ApiErrorOptions) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    this.requestId = options.requestId;
  }
}

/**
 * Maps a backend `ErrorResponse` envelope, plus the HTTP status it arrived
 * with, to an `ApiError`.
 */
export function toApiError(status: number, body: ErrorResponse): ApiError {
  return new ApiError({
    status,
    code: body.error.code,
    message: body.error.message,
    details: body.error.details,
    requestId: body.request_id,
  });
}

/**
 * Builds an `ApiError` for a transport failure that never produced a parsed
 * envelope, such as a network error or a non-JSON response.
 */
export function toUnknownApiError(status: number, message: string): ApiError {
  return new ApiError({ status, code: "unknown_error", message, details: null, requestId: null });
}
