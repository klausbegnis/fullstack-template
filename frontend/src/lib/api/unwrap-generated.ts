/**
 * Casts the result of a generated orval call to its actual, already-unwrapped
 * runtime shape. `apiMutator` unwraps the backend's `SuccessResponse`
 * envelope at the HTTP boundary, but orval's generated return types describe
 * the wire shape before that unwrap (there is no way to tell orval about a
 * mutator's runtime behavior), so every generated call whose OpenAPI schema
 * is `SuccessResponse<T>` needs this one explicit, documented correction.
 * Calls whose schema is a bare object or a `PaginatedResponse` need no cast —
 * `apiMutator` passes those through unchanged.
 */
export function unwrapGenerated<TData>(response: unknown): TData {
  return response as TData;
}
