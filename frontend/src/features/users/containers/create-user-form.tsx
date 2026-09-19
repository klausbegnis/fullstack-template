"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createUserSchema } from "@/features/users/model/user-schema";
import type { CreateUserInput, CreateUserValues } from "@/features/users/model/user-schema";
import { useCreateUser } from "@/features/users/api/use-create-user";
import { UserFormView } from "@/features/users/components/user-form-view";
import { applyFieldErrors } from "@/lib/errors/field-errors";

/**
 * Wires the create-user form: validation, submission through `useMutation`,
 * and a redirect to the new user's detail page on success.
 */
export function CreateUserForm() {
  const router = useRouter();
  const mutation = useCreateUser();
  const form = useForm<CreateUserInput, unknown, CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { name: "", email: "", password: "", role: "member" },
  });

  const submit = form.handleSubmit(async (values) => {
    try {
      const user = await mutation.mutateAsync(values);
      router.push(`/users/${user.id}`);
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
      includePassword
      submitLabel="Create user"
    />
  );
}
