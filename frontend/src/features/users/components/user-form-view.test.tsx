import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import type { FormEventHandler } from "react";
import { describe, expect, it, vi } from "vitest";
import { UserFormView } from "@/features/users/components/user-form-view";

interface HarnessValues {
  name: string;
  email: string;
  password: string;
  role: string;
}

interface HarnessProps {
  includePassword: boolean;
  formError: string | null;
  onSubmit: () => void;
  heading?: string;
}

function Harness({ includePassword, formError, onSubmit, heading }: HarnessProps) {
  const form = useForm<HarnessValues>({
    defaultValues: { name: "", email: "", password: "", role: "member" },
  });

  const handleSubmit: FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <UserFormView
      register={form.register}
      errors={form.formState.errors}
      formError={formError}
      isSubmitting={false}
      onSubmit={handleSubmit}
      includePassword={includePassword}
      submitLabel="Create user"
      heading={heading}
    />
  );
}

describe("UserFormView", () => {
  it("labels every field and submits through the handler it was given", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<Harness includePassword formError={null} onSubmit={onSubmit} />);

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Role")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create user" }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("heads the form with the heading it was given, and with none by default", () => {
    const { unmount } = render(
      <Harness includePassword formError={null} onSubmit={vi.fn()} heading="New user" />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "New user" })).toBeInTheDocument();
    unmount();

    render(<Harness includePassword formError={null} onSubmit={vi.fn()} />);
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("omits the password field and announces the form-level error", () => {
    render(<Harness includePassword={false} formError="Email already taken" onSubmit={vi.fn()} />);

    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Email already taken");
  });
});
