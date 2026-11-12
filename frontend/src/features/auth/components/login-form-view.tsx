import type { FormEventHandler } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { LoginInput } from "@/features/auth/model/login-schema";

export interface LoginFormViewProps {
  register: UseFormRegister<LoginInput>;
  errors: FieldErrors<LoginInput>;
  formError: string | null;
  sessionExpired?: boolean;
  isSubmitting: boolean;
  onSubmit: FormEventHandler<HTMLFormElement>;
}

/**
 * Renders the login form's markup from props only. Field wiring, validation
 * and submission all live in the container — code crosses through imports,
 * data crosses through props. `sessionExpired` announces that the previous
 * session ended on its own.
 */
export function LoginFormView({
  register,
  errors,
  formError,
  sessionExpired = false,
  isSubmitting,
  onSubmit,
}: LoginFormViewProps) {
  return (
    <form {...{ onSubmit }} noValidate className="flex w-full max-w-sm flex-col gap-4">
      <h1 className="text-lg font-semibold text-gray-900">Sign in</h1>
      {sessionExpired ? (
        <p role="status" className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-900">
          Your session expired. Sign in again.
        </p>
      ) : null}
      {formError ? <Alert tone="danger" title={formError} /> : null}
      <Field id="email" label="Email" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
      </Field>
      <Field id="password" label="Password" error={errors.password?.message}>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? "password-error" : undefined}
          {...register("password")}
        />
      </Field>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
