import type { FormEventHandler } from "react";
import type { FieldErrors, FieldValues, Path, UseFormRegister } from "react-hook-form";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export interface UserFormViewProps<TFieldValues extends FieldValues> {
  register: UseFormRegister<TFieldValues>;
  errors: FieldErrors<TFieldValues>;
  formError: string | null;
  isSubmitting: boolean;
  onSubmit: FormEventHandler<HTMLFormElement>;
  includePassword: boolean;
  submitLabel: string;
}

/**
 * Renders the shared create/edit user form markup from props only. The
 * container decides which schema, mutation and default values apply.
 */
export function UserFormView<TFieldValues extends FieldValues>({
  register,
  errors,
  formError,
  isSubmitting,
  onSubmit,
  includePassword,
  submitLabel,
}: UserFormViewProps<TFieldValues>) {
  const nameField = "name" as Path<TFieldValues>;
  const emailField = "email" as Path<TFieldValues>;
  const passwordField = "password" as Path<TFieldValues>;
  const roleField = "role" as Path<TFieldValues>;

  return (
    <form {...{ onSubmit }} noValidate className="flex max-w-sm flex-col gap-4">
      {formError ? <Alert tone="danger" title={formError} /> : null}
      <Field id="name" label="Name" error={errors.name?.message as string | undefined}>
        <Input id="name" autoComplete="name" {...register(nameField)} />
      </Field>
      <Field id="email" label="Email" error={errors.email?.message as string | undefined}>
        <Input id="email" type="email" autoComplete="email" {...register(emailField)} />
      </Field>
      {includePassword ? (
        <Field
          id="password"
          label="Password"
          error={errors.password?.message as string | undefined}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...register(passwordField)}
          />
        </Field>
      ) : null}
      <Field id="role" label="Role" error={errors.role?.message as string | undefined}>
        <select
          id="role"
          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          {...register(roleField)}
        >
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>
      </Field>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
