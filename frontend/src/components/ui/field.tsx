import type { ReactNode } from "react";

export interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

/**
 * Wraps a form control with its label, hint and error text. It renders
 * whatever control is passed as `children` — an `Input`, a `select`, a
 * custom control — and never calls a form library itself.
 */
export function Field({ id, label, error, hint, children }: FieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-gray-900">
        {label}
      </label>
      {children}
      {hint ? (
        <p id={hintId} className="text-xs text-gray-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
