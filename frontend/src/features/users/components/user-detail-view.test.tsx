import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { UserDetailView } from "@/features/users/components/user-detail-view";
import { buildUser } from "@/features/users/testing/factories";

function renderView(user: ReturnType<typeof buildUser>) {
  render(
    <UserDetailView
      user={user}
      editForm={<p>Edit form</p>}
      disableControl={<button type="button">Disable user</button>}
    />,
  );
}

describe("UserDetailView", () => {
  it("shows the user's name, email, role and active status", () => {
    renderView(buildUser({ name: "Ada Lovelace", email: "ada@example.com", role: "admin" }));

    expect(screen.getByRole("heading", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("admin · Active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable user" })).toBeInTheDocument();
    expect(screen.getByText("Edit form")).toBeInTheDocument();
  });

  it("heads a user without a name with the local part of their email", () => {
    renderView(buildUser({ name: "", email: "root@example.com" }));

    expect(screen.getByRole("heading", { level: 1, name: "root" })).toBeInTheDocument();
  });

  it("hides the disable control once the user is disabled", () => {
    renderView(buildUser({ role: "member", disabledAt: new Date("2026-02-01T00:00:00Z") }));

    expect(screen.getByText("member · Disabled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disable user" })).not.toBeInTheDocument();
  });
});
