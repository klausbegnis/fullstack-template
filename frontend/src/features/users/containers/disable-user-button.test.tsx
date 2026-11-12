import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DisableUserButton } from "@/features/users/containers/disable-user-button";
import { server } from "@/testing/msw/server";
import { renderWithProviders } from "@/testing/render";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push: vi.fn() }) }));

const disabledResponse = () =>
  HttpResponse.json({ success: true, message: "User disabled", data: null });

beforeEach(() => {
  refresh.mockClear();
});

describe("DisableUserButton", () => {
  it("asks for confirmation before disabling", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);
    expect(screen.queryByRole("dialog", { name: "Disable this user?" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Disable user" }));

    const dialog = screen.getByRole("dialog", { name: "Disable this user?" });
    expect(dialog).toHaveTextContent("They will no longer be able to sign in.");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("closes on Cancel without a request and gives focus back to the trigger", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);
    const trigger = screen.getByRole("button", { name: "Disable user" });
    await user.click(trigger);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);
    await user.click(screen.getByRole("button", { name: "Disable user" }));

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("disables the user on confirmation and refreshes the route", async () => {
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

    await user.click(screen.getByRole("button", { name: "Disable" }));

    await waitFor(() => {
      expect(refresh).toHaveBeenCalledOnce();
    });
    expect(requestedUrl).toContain("/users/u-1");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the dialog open and shows why when disabling fails", async () => {
    server.use(
      http.delete("*/users/:userId", () =>
        HttpResponse.json(
          {
            success: false,
            error: {
              code: "conflict",
              message: "The last admin cannot be disabled",
              details: null,
            },
          },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);
    await user.click(screen.getByRole("button", { name: "Disable user" }));

    await user.click(screen.getByRole("button", { name: "Disable" }));

    const dialog = screen.getByRole("dialog", { name: "Disable this user?" });
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "The last admin cannot be disabled",
    );
    expect(refresh).not.toHaveBeenCalled();
  });

  it("blocks a second confirmation while the request is in flight", async () => {
    let calls = 0;
    let release = () => {};
    const released = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.delete("*/users/:userId", async () => {
        calls += 1;
        await released;
        return disabledResponse();
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<DisableUserButton userId="u-1" />);
    await user.click(screen.getByRole("button", { name: "Disable user" }));

    await user.click(screen.getByRole("button", { name: "Disable" }));

    expect(await screen.findByRole("button", { name: "Disabling…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "Disable this user?" })).toBeInTheDocument();
    release();
    await waitFor(() => {
      expect(refresh).toHaveBeenCalled();
    });
    expect(calls).toBe(1);
  });
});
