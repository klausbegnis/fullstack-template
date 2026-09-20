import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { DisableUserButton } from "@/features/users/containers/disable-user-button";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push: vi.fn() }) }));

const disabledResponse = () =>
  HttpResponse.json({ success: true, message: "User disabled", data: null });

describe("DisableUserButton", () => {
  it("disables the user and refreshes the route", async () => {
    let requestedUrl = "";
    server.use(
      http.delete("*/users/:userId", ({ request }) => {
        requestedUrl = request.url;
        return disabledResponse();
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);

    await user.click(screen.getByRole("button", { name: "Disable user" }));

    await waitFor(() => {
      expect(refresh).toHaveBeenCalledOnce();
    });
    expect(requestedUrl).toContain("/users/u-1");
  });

  it("blocks a second click while the request is in flight", async () => {
    let calls = 0;
    server.use(
      http.delete("*/users/:userId", async () => {
        calls += 1;
        await delay(20);
        return disabledResponse();
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);

    await user.click(screen.getByRole("button", { name: "Disable user" }));

    expect(await screen.findByRole("button", { name: "Disabling…" })).toBeDisabled();

    await waitFor(() => {
      expect(refresh).toHaveBeenCalled();
    });
    expect(calls).toBe(1);
  });
});
