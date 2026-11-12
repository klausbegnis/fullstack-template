import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/app-shell";
import type { NavItem } from "@/components/layout/nav-items";

const location = vi.hoisted(() => ({ pathname: "/items/42" }));

vi.mock("next/navigation", () => ({
  usePathname: () => location.pathname,
}));

afterEach(() => {
  location.pathname = "/items/42";
});

const SIDEBAR_ONLY: NavItem[] = [
  { href: "/items", label: "Items", icon: "▤" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

const WITH_TABS: NavItem[] = [
  { href: "/items", label: "Items", icon: "▤", phoneTab: "Items" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

function shell(items: NavItem[] = SIDEBAR_ONLY) {
  return (
    <AppShell
      productName="Example App"
      items={items}
      accountMenu={<button type="button">Account of Visitor</button>}
    >
      <p>Main content</p>
    </AppShell>
  );
}

describe("AppShell", () => {
  it("names the product once in the single header row with the account menu and menu button", () => {
    render(shell());
    const header = screen.getByRole("banner");

    expect(within(header).getAllByText("Example App")).toHaveLength(1);
    expect(within(header).getByRole("button", { name: "Account of Visitor" })).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-controls",
      "app-menu",
    );
  });

  it("renders the content in the main landmark the skip link targets", () => {
    render(shell());

    expect(screen.getByRole("main")).toHaveTextContent("Main content");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
  });

  it("marks the entry the current path belongs to", () => {
    render(shell());

    expect(screen.getByRole("link", { name: "Items" })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { current: "page" })).toHaveLength(1);
  });

  it("opens the menu with the navigation and closes it on Escape", async () => {
    const user = userEvent.setup();
    render(shell());
    const toggle = screen.getByRole("button", { name: "Open menu" });

    await user.click(toggle);

    expect(toggle).toHaveAccessibleName("Close menu");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("complementary", { name: "Menu" });
    expect(menu).toHaveFocus();
    expect(within(menu).getByRole("navigation", { name: "Primary" })).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
  });

  it("closes the menu when the path changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(shell());
    await user.click(screen.getByRole("button", { name: "Open menu" }));

    location.pathname = "/settings";
    rerender(shell());

    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("keeps the desktop-only sidebar breakpoint and no tab bar without phone tabs", () => {
    render(shell());

    expect(screen.getByRole("button", { name: "Open menu" })).toHaveClass("lg:hidden");
    expect(screen.queryByRole("navigation", { name: "Tabs" })).toBeNull();
  });

  it("adds the phone tab bar outside the menu and moves the sidebar to the tablet breakpoint", async () => {
    const user = userEvent.setup();
    render(shell(WITH_TABS));
    const toggle = screen.getByRole("button", { name: "Open menu" });

    expect(toggle).toHaveClass("md:hidden");
    await user.click(toggle);

    const menu = screen.getByRole("complementary", { name: "Menu" });
    expect(within(menu).queryByRole("navigation", { name: "Tabs" })).toBeNull();
    const tabs = screen.getByRole("navigation", { name: "Tabs" });
    expect(within(tabs).getByRole("link", { name: "Items" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
