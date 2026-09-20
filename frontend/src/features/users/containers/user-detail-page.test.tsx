import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { UserDetailPage } from "@/features/users/containers/user-detail-page";
import { buildUserDto } from "@/features/users/testing/factories";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));

describe("UserDetailPage", () => {
  it("renders the user returned by the API with its edit and disable controls", async () => {
    server.use(
      http.get("*/users/:userId", () =>
        HttpResponse.json({
          success: true,
          message: "User",
          data: buildUserDto({ id: "u-1", name: "Ada Lovelace", email: "ada@example.com" }),
        }),
      ),
    );

    renderWithProviders(<UserDetailPage userId="u-1" />);

    expect(await screen.findByRole("heading", { name: "Ada Lovelace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable user" })).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    server.use(
      http.get("*/users/:userId", () =>
        HttpResponse.json(
          { error: { code: "internal_error", message: "boom", details: null }, request_id: null },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<UserDetailPage userId="u-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load user");
  });
});
