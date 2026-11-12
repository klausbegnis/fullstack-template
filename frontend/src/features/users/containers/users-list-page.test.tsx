import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { UsersListPage } from "@/features/users/containers/users-list-page";
import { buildPaginatedUsersDto, buildUserDto } from "@/features/users/testing/factories";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

describe("UsersListPage", () => {
  it("renders the users returned by the API", async () => {
    server.use(
      http.get("*/users", () =>
        HttpResponse.json(
          buildPaginatedUsersDto([buildUserDto({ id: "a1", name: "Ada Lovelace" })]),
        ),
      ),
    );

    renderWithProviders(<UsersListPage />);

    expect(await screen.findByRole("link", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Users pagination" })).not.toBeInTheDocument();
  });

  it("requests the page chosen in the pager", async () => {
    const requestedPages: string[] = [];
    server.use(
      http.get("*/users", ({ request }) => {
        const page = new URL(request.url).searchParams.get("page") ?? "1";
        requestedPages.push(page);
        return HttpResponse.json({
          ...buildPaginatedUsersDto([buildUserDto({ name: `User on page ${page}` })]),
          total: 45,
          page: Number(page),
          page_size: 20,
          total_pages: 3,
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<UsersListPage />);
    await screen.findByRole("link", { name: "User on page 1" });

    await user.click(screen.getByRole("button", { name: "Page 3" }));

    expect(await screen.findByRole("link", { name: "User on page 3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 3" })).toHaveAttribute("aria-current", "page");
    expect(requestedPages).toEqual(["1", "3"]);
  });

  it("shows the empty state when there are no users", async () => {
    server.use(http.get("*/users", () => HttpResponse.json(buildPaginatedUsersDto([]))));

    renderWithProviders(<UsersListPage />);

    expect(await screen.findByRole("heading", { name: "No users yet" })).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    server.use(
      http.get("*/users", () =>
        HttpResponse.json(
          { error: { code: "internal_error", message: "boom", details: null }, request_id: null },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<UsersListPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load users");
  });
});
