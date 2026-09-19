import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UsersListView } from "@/features/users/components/users-list-view";
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

describe("UsersListView", () => {
  it("lists each user by name, email and status", () => {
    render(
      <UsersListView
        users={users}
        status="ready"
        page={1}
        totalPages={2}
        canGoToPreviousPage={false}
        canGoToNextPage={true}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    );

    expect(screen.getByRole("link", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(screen.getByText("grace@example.com")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows a spinner while loading and no table", () => {
    render(
      <UsersListView
        users={[]}
        status="loading"
        page={1}
        totalPages={1}
        canGoToPreviousPage={false}
        canGoToNextPage={false}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows an error alert when loading failed", () => {
    render(
      <UsersListView
        users={[]}
        status="error"
        page={1}
        totalPages={1}
        canGoToPreviousPage={false}
        canGoToNextPage={false}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load users");
  });

  it("reports the page the caller requested", async () => {
    const user = userEvent.setup();
    const onNextPage = vi.fn();
    render(
      <UsersListView
        users={users}
        status="ready"
        page={1}
        totalPages={2}
        canGoToPreviousPage={false}
        canGoToNextPage={true}
        onPreviousPage={vi.fn()}
        onNextPage={onNextPage}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(onNextPage).toHaveBeenCalledOnce();
  });

  it("disables the previous button on the first page", () => {
    render(
      <UsersListView
        users={users}
        status="ready"
        page={1}
        totalPages={2}
        canGoToPreviousPage={false}
        canGoToNextPage={true}
        onPreviousPage={vi.fn()}
        onNextPage={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});
