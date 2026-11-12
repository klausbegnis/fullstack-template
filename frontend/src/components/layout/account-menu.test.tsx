import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AccountMenu } from "@/components/layout/account-menu";

const logout = vi.fn();

function menu() {
  return (
    <>
      <AccountMenu userName="Ada King Lovelace" userEmail="ada@example.com">
        <a href="/profile" role="menuitem" tabIndex={-1}>
          Profile
        </a>
        <button type="button" role="menuitem" tabIndex={-1} onClick={logout}>
          Log out
        </button>
      </AccountMenu>
      <p>Outside the menu</p>
    </>
  );
}

describe("AccountMenu", () => {
  it("shows the user's initials on a button named after them, closed", () => {
    render(menu());
    const avatar = screen.getByRole("button", { name: "Account of Ada King Lovelace" });

    expect(avatar).toHaveTextContent("AL");
    expect(avatar).toHaveAttribute("aria-haspopup", "menu");
    expect(avatar).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("opens with the name and email, then the items, first item focused", async () => {
    const user = userEvent.setup();
    render(menu());
    const avatar = screen.getByRole("button", { name: "Account of Ada King Lovelace" });

    await user.click(avatar);

    expect(avatar).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    const items = within(screen.getByRole("menu")).getAllByRole("menuitem");
    expect(items.map((item) => item.textContent)).toEqual(["Profile", "Log out"]);
    expect(items[0]).toHaveFocus();
  });

  it("moves between items with the arrow keys, Home and End", async () => {
    const user = userEvent.setup();
    render(menu());
    await user.click(screen.getByRole("button", { name: "Account of Ada King Lovelace" }));

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Log out" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Profile" })).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("menuitem", { name: "Log out" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("menuitem", { name: "Profile" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(screen.getByRole("menuitem", { name: "Log out" })).toHaveFocus();
  });

  it("closes on Escape and gives focus back to the avatar", async () => {
    const user = userEvent.setup();
    render(menu());
    const avatar = screen.getByRole("button", { name: "Account of Ada King Lovelace" });
    await user.click(avatar);

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).toBeNull();
    expect(avatar).toHaveAttribute("aria-expanded", "false");
    expect(avatar).toHaveFocus();
  });

  it("closes on a pointer outside it", async () => {
    const user = userEvent.setup();
    render(menu());
    await user.click(screen.getByRole("button", { name: "Account of Ada King Lovelace" }));

    await user.click(screen.getByText("Outside the menu"));

    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("runs an item's own action", async () => {
    const user = userEvent.setup();
    render(menu());
    await user.click(screen.getByRole("button", { name: "Account of Ada King Lovelace" }));

    await user.click(screen.getByRole("menuitem", { name: "Log out" }));

    expect(logout).toHaveBeenCalled();
  });
});
