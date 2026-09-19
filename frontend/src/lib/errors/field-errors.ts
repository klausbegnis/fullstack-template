import { ApiError } from "@/lib/errors/api-error";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

interface ValidationIssue {
  type: string;
  loc: Array<string | number>;
  msg: string;
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as ValidationIssue).loc) &&
    typeof (value as ValidationIssue).msg === "string"
  );
}

function readValidationIssues(details: Record<string, unknown> | null): ValidationIssue[] {
  const candidate = details?.errors;
  if (!Array.isArray(candidate)) return [];
  return candidate.filter(isValidationIssue);
}

/**
 * Maps a FastAPI 422 body's `error.details.errors[].loc` path onto the
 * matching form field with `setError`, so backend validation lands on the
 * right input, and returns the form-level message to display above the
 * form. Any error that is not an `ApiError` yields a generic message.
 */
export function applyFieldErrors<TFieldValues extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<TFieldValues>,
): string {
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Please try again.";
  }

  for (const issue of readValidationIssues(error.details)) {
    const field = issue.loc.filter((segment) => segment !== "body").join(".");
    if (field.length > 0) {
      setError(field as Path<TFieldValues>, { type: "server", message: issue.msg });
    }
  }

  return error.message;
}
