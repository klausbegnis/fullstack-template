import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { EditUserForm } from "@/features/users/containers/edit-user-form";
import { buildUser, buildUserDto } from "@/features/users/testing/factories";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

const existingUser = () =>
  buildUser({ id: "u-1", name: "Ada Lovelace", email: "ada@example.com", role: "member" });

describe("EditUserForm", () => {
  it("prefills the form and sends the edited fields", async () => {
    let received: unknown;
    server.use(
      http.patch("*/users/:userId", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({
          success: true,
          message: "User updated",
          data: buildUserDto({ id: "u-1", name: "Ada L." }),
        });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<EditUserForm user={existingUser()} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Ada Lovelace");
    expect(screen.getByLabelText("Email")).toHaveValue("ada@example.com");

    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Ada L.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(received).toEqual({ name: "Ada L.", email: "ada@example.com", role: "member" });
    });
  });

  it("shows a form-level error when the backend rejects the change", async () => {
    server.use(
      http.patch("*/users/:userId", () =>
        HttpResponse.json(
          {
            error: { code: "conflict", message: "That email is already taken", details: null },
            request_id: null,
          },
          { status: 409 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(<EditUserForm user={existingUser()} />);

    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("That email is already taken")).toBeInTheDocument();
  });
});
