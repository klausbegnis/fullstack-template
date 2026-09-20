import { screen } from "@testing-library/react";
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
    expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
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
