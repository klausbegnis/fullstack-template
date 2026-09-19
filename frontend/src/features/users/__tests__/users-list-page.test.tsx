import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";
import { UsersListPage } from "@/features/users/containers/users-list-page";

describe("UsersListPage", () => {
  it("renders the users returned by the API", async () => {
    server.use(
      http.get("*/users", () =>
        HttpResponse.json({
          success: true,
          data: [
            {
              id: "a1",
              name: "Ada Lovelace",
              email: "ada@example.com",
              role: "admin",
              disabled_at: null,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          total_pages: 1,
        }),
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
