import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import type { FormEventHandler } from "react";
import { describe, expect, it, vi } from "vitest";
import { LoginFormView } from "@/features/auth/components/login-form-view";
import type { LoginInput } from "@/features/auth/model/login-schema";

interface HarnessProps {
  formError: string | null;
  sessionExpired?: boolean;
  isSubmitting: boolean;
  onSubmit: () => void;
}

function Harness({ formError, sessionExpired, isSubmitting, onSubmit }: HarnessProps) {
  const form = useForm<LoginInput>({ defaultValues: { email: "", password: "" } });

  const handleSubmit: FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <LoginFormView
      register={form.register}
      errors={form.formState.errors}
      formError={formError}
      sessionExpired={sessionExpired}
      isSubmitting={isSubmitting}
      onSubmit={handleSubmit}
    />
  );
}

describe("LoginFormView", () => {
  it("labels both credentials and submits through the handler it was given", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Harness formError={null} isSubmitting={false} onSubmit={onSubmit} />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("announces the form-level error and disables the button while submitting", () => {
    render(<Harness formError="Invalid email or password" isSubmitting onSubmit={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password");
    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
  });

  it("tells the visitor only when the session expired on its own", () => {
    const { rerender } = render(
      <Harness formError={null} isSubmitting={false} onSubmit={vi.fn()} />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    rerender(<Harness formError={null} sessionExpired isSubmitting={false} onSubmit={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Your session expired. Sign in again.");
  });
});
