import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UsersListView, type UsersPagerProps } from "@/features/users/components/users-list-view";
import type { User } from "@/features/users/model/user";

const users: User[] = [
  {
    id: "a1",
    name: "Ada Lovelace",
    email: "ada@example.com",
    role: "admin",
    disabledAt: null,
    createdAt: new Date("2026-01-01T00:00:00Z"),
    updatedAt: new Date("2026-01-01T00:00:00Z"),
  },
  {
    id: "a2",
    name: "Grace Hopper",
    email: "grace@example.com",
    role: "member",
    disabledAt: new Date("2026-01-05T00:00:00Z"),
    createdAt: new Date("2026-01-01T00:00:00Z"),
    updatedAt: new Date("2026-01-01T00:00:00Z"),
  },
];

function pager(overrides: Partial<UsersPagerProps> = {}): UsersPagerProps {
  return {
    page: 1,
    pageCount: 3,
    totalItems: 45,
    pageSize: 20,
    onPageChange: vi.fn(),
    ...overrides,
  };
}

describe("UsersListView", () => {
  it("lists each user by name, email and status", () => {
    render(<UsersListView users={users} status="ready" pager={pager()} />);

    expect(screen.getByRole("link", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(screen.getByText("grace@example.com")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows a spinner while loading and no table", () => {
    render(<UsersListView users={[]} status="loading" pager={pager()} />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows an error alert when loading failed", () => {
    render(<UsersListView users={[]} status="error" pager={pager()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load users");
  });

  it("shows an empty state with a create link when there are no users", () => {
    render(
      <UsersListView users={[]} status="ready" pager={pager({ totalItems: 0, pageCount: 1 })} />,
    );

    expect(screen.getByRole("heading", { level: 2, name: "No users yet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create the first user" })).toHaveAttribute(
      "href",
      "/users/new",
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("pages through the shared pager and reports the page asked for", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<UsersListView users={users} status="ready" pager={pager({ onPageChange })} />);

    expect(screen.getByRole("navigation", { name: "Users pagination" })).toHaveTextContent(
      "Showing 1–20 of 45 users",
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Page 3" }));

    expect(onPageChange.mock.calls).toEqual([[2], [3]]);
  });

  it("hides the pager when every user fits on one page", () => {
    render(
      <UsersListView users={users} status="ready" pager={pager({ totalItems: 2, pageCount: 1 })} />,
    );

    expect(screen.queryByRole("navigation", { name: "Users pagination" })).not.toBeInTheDocument();
  });
});
