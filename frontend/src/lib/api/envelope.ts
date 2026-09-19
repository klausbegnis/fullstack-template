export interface SuccessResponse<TData> {
  success: true;
  message: string;
  data: TData;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
  request_id: string | null;
}

export interface PaginatedResponse<TItem> {
  success: true;
  data: TItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type Envelope<TData> = SuccessResponse<TData> | ErrorResponse;

/**
 * Narrows an envelope to its error branch, matching the backend's
 * `{ error: { code, message, details }, request_id }` shape.
 */
export function isErrorResponse(envelope: unknown): envelope is ErrorResponse {
  return typeof envelope === "object" && envelope !== null && "error" in envelope;
}

/**
 * Narrows an envelope to its paginated branch.
 */
export function isPaginatedResponse<TItem>(
  envelope: unknown,
): envelope is PaginatedResponse<TItem> {
  return (
    typeof envelope === "object" &&
    envelope !== null &&
    "total_pages" in envelope &&
    "page" in envelope
  );
}

/**
 * Narrows an envelope to its plain success branch. Some endpoints (`/auth/login`,
 * `/auth/me`) return the resource bare, with no envelope at all, so callers must
 * check this rather than assuming every success body is wrapped.
 */
export function isSuccessResponse<TData>(envelope: unknown): envelope is SuccessResponse<TData> {
  return (
    typeof envelope === "object" &&
    envelope !== null &&
    "success" in envelope &&
    "data" in envelope &&
    !("total_pages" in envelope)
  );
}

/**
 * Extracts the `data` payload from a success envelope, throwing if the
 * envelope is an error branch. Callers that already know the shape of the
 * envelope should prefer reading `.data` directly.
 */
export function unwrapEnvelope<TData>(envelope: Envelope<TData>): TData {
  if (isErrorResponse(envelope)) {
    throw new Error(envelope.error.message);
  }
  return envelope.data;
}
