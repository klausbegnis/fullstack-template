import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LogoutButton } from "@/features/auth/containers/logout-button";
import { logoutAction } from "@/features/auth/actions/logout-action";

vi.mock("@/features/auth/actions/logout-action", () => ({
  logoutAction: vi.fn(async () => undefined),
}));

describe("LogoutButton", () => {
  it("renders a submit control with an accessible name", () => {
    render(<LogoutButton />);

    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });

  it("runs the logout Server Action when submitted", async () => {
    const user = userEvent.setup();
    render(<LogoutButton />);

    await user.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => {
      expect(logoutAction).toHaveBeenCalled();
    });
  });

  it("renders as a menu item for a menu", () => {
    render(
      <div role="menu" aria-label="Account">
        <LogoutButton variant="menuitem" />
      </div>,
    );

    expect(screen.getByRole("menuitem", { name: "Log out" })).toHaveAttribute("type", "submit");
  });
});
