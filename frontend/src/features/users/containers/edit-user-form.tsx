"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { updateUserSchema } from "@/features/users/model/user-schema";
import type { UpdateUserInput, UpdateUserValues } from "@/features/users/model/user-schema";
import { useUpdateUser } from "@/features/users/api/use-update-user";
import { UserFormView } from "@/features/users/components/user-form-view";
import { applyFieldErrors } from "@/lib/errors/field-errors";
import type { User } from "@/features/users/model/user";

export interface EditUserFormProps {
  user: User;
}

/**
 * Wires the edit-user form, pre-filled from the user passed down by the
 * detail container, and submits through `useMutation`.
 */
export function EditUserForm({ user }: EditUserFormProps) {
  const mutation = useUpdateUser();
  const form = useForm<UpdateUserInput, unknown, UpdateUserValues>({
    resolver: zodResolver(updateUserSchema),
    defaultValues: { name: user.name, email: user.email, role: user.role },
  });

  const submit = form.handleSubmit(async (values) => {
    try {
      await mutation.mutateAsync({ userId: user.id, values });
    } catch (error) {
      const message = applyFieldErrors(error, form.setError);
      form.setError("root", { type: "server", message });
    }
  });

  return (
    <UserFormView
      register={form.register}
      errors={form.formState.errors}
      formError={form.formState.errors.root?.message ?? null}
      isSubmitting={form.formState.isSubmitting}
      onSubmit={submit}
      includePassword={false}
      submitLabel="Save changes"
    />
  );
}
