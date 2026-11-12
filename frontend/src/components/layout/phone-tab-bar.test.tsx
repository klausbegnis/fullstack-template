import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PhoneTabBar } from "@/components/layout/phone-tab-bar";
import type { PhoneTabItem } from "@/components/layout/nav-items";

const TABS: PhoneTabItem[] = [
  { href: "/", label: "Home", icon: "⌂", phoneTab: "Home" },
  { href: "/items", label: "All items", icon: "▤", phoneTab: "Items" },
];

describe("PhoneTabBar", () => {
  it("links each tab by its short label", () => {
    render(<PhoneTabBar tabs={TABS} activeHref="/" />);
    const tabs = screen.getByRole("navigation", { name: "Tabs" });

    expect(
      within(tabs)
        .getAllByRole("link")
        .map((link) => [link.textContent?.replace(/^[^\p{L}]+/u, ""), link.getAttribute("href")]),
    ).toEqual([
      ["Home", "/"],
      ["Items", "/items"],
    ]);
  });

  it("marks only the active destination as the current page", () => {
    render(<PhoneTabBar tabs={TABS} activeHref="/items" />);

    expect(screen.getByRole("link", { name: "Items" })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { current: "page" })).toHaveLength(1);
  });

  it("marks no tab on a page outside the tabs", () => {
    render(<PhoneTabBar tabs={TABS} activeHref={null} />);

    expect(screen.queryAllByRole("link", { current: "page" })).toHaveLength(0);
  });
});
