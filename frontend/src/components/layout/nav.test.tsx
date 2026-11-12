import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Nav } from "@/components/layout/nav";
import type { NavItem } from "@/components/layout/nav-items";

const ITEMS: NavItem[] = [
  { href: "/items", label: "Items", icon: "▤" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

describe("Nav", () => {
  it("links every destination by its label", () => {
    render(<Nav items={ITEMS} activeHref={null} />);
    const nav = screen.getByRole("navigation", { name: "Primary" });

    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Items" })).toHaveAttribute("href", "/items");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.queryAllByRole("link", { current: "page" })).toHaveLength(0);
  });

  it("marks only the active destination as the current page", () => {
    render(<Nav items={ITEMS} activeHref="/settings" />);

    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link", { current: "page" })).toHaveLength(1);
  });
});
