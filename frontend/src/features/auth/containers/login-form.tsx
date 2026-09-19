"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { loginAction } from "@/features/auth/actions/login-action";
import { loginSchema } from "@/features/auth/model/login-schema";
import type { LoginInput, LoginValues } from "@/features/auth/model/login-schema";
import { LoginFormView } from "@/features/auth/components/login-form-view";

/**
 * Wires the login form's validation and submission. Login is a React 19
 * Action rather than a `useMutation` call because writing the httpOnly
 * session cookie is something only the Next server can do.
 */
export function LoginForm() {
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<LoginInput, unknown, LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    const result = await loginAction(values);
    if (result.status === "error") {
      setFormError(result.message);
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <LoginFormView
        register={form.register}
        errors={form.formState.errors}
        formError={formError}
        isSubmitting={form.formState.isSubmitting}
        onSubmit={submit}
      />
    </div>
  );
}
