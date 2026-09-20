import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { CreateUserForm } from "@/features/users/containers/create-user-form";
import { buildUserDto } from "@/features/users/testing/factories";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Name"), "Ada Lovelace");
  await user.type(screen.getByLabelText("Email"), "ada@example.com");
  await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
  await user.click(screen.getByRole("button", { name: "Create user" }));
}

describe("CreateUserForm", () => {
  it("creates the user and redirects to the new detail page", async () => {
    const created = buildUserDto({ id: "u-1", name: "Ada Lovelace", email: "ada@example.com" });
    server.use(
      http.post("*/users", () =>
        HttpResponse.json(
          { success: true, message: "User created", data: created },
          { status: 201 },
        ),
      ),
    );

    renderWithProviders(<CreateUserForm />);
    await fillAndSubmit();

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/users/u-1");
    });
  });

  it("puts a backend validation error on the field it belongs to", async () => {
    server.use(
      http.post("*/users", () =>
        HttpResponse.json(
          {
            error: {
              code: "validation_error",
              message: "Could not create the user",
              details: {
                errors: [
                  { type: "value_error", loc: ["body", "email"], msg: "Email already registered" },
                ],
              },
            },
            request_id: null,
          },
          { status: 422 },
        ),
      ),
    );

    renderWithProviders(<CreateUserForm />);
    await fillAndSubmit();

    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    expect(await screen.findByText("Could not create the user")).toBeInTheDocument();
  });
});
