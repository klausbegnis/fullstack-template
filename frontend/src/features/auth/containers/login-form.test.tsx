import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/features/auth/containers/login-form";
import { loginAction } from "@/features/auth/actions/login-action";

vi.mock("@/features/auth/actions/login-action", () => ({
  loginAction: vi.fn(),
}));

describe("LoginForm", () => {
  it("shows an inline validation error and never calls the action", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "not-an-email");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(loginAction).not.toHaveBeenCalled();
  });

  it("surfaces a failed login as a form-level error", async () => {
    vi.mocked(loginAction).mockResolvedValue({
      status: "error",
      message: "Invalid email or password",
    });

    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });

  it("hands the return path to the action and shows the expired notice", async () => {
    vi.mocked(loginAction).mockResolvedValue({ status: "error", message: "Try again" });

    const user = userEvent.setup();
    render(<LoginForm returnTo="/users?page=2" sessionExpired />);

    expect(screen.getByRole("status")).toHaveTextContent("Your session expired. Sign in again.");
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await screen.findByText("Try again");
    expect(loginAction).toHaveBeenLastCalledWith(
      { email: "ada@example.com", password: "secret" },
      "/users?page=2",
    );
  });
});
