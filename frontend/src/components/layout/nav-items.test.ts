import { describe, expect, it } from "vitest";
import {
  activeNavHref,
  navItems,
  phoneTabItems,
  type NavItem,
} from "@/components/layout/nav-items";

const ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: "⌂", phoneTab: "Home" },
  { href: "/items", label: "Items", icon: "▤", phoneTab: "Items" },
  { href: "/items/archive", label: "Archive", icon: "▧" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

describe("navItems", () => {
  it("lists every destination with a label, an icon and an absolute href", () => {
    for (const item of navItems) {
      expect(item.href.startsWith("/")).toBe(true);
      expect(item.label).not.toBe("");
      expect(item.icon).not.toBe("");
    }
  });
});

describe("phoneTabItems", () => {
  it("keeps only the entries with a phone tab label, in order", () => {
    expect(phoneTabItems(ITEMS).map((item) => item.phoneTab)).toEqual(["Home", "Items"]);
  });
});

describe("activeNavHref", () => {
  it.each([
    ["/", "/"],
    ["/items", "/items"],
    ["/items/42", "/items"],
    ["/items/archive/7", "/items/archive"],
    ["/itemsx", "/"],
    ["/settings", "/settings"],
  ])("marks %s as part of %s", (pathname, href) => {
    expect(activeNavHref(ITEMS, pathname)).toBe(href);
  });

  it("marks nothing when no entry matches or the path is unknown", () => {
    expect(activeNavHref(ITEMS.slice(1), "/elsewhere")).toBeNull();
    expect(activeNavHref(ITEMS, null)).toBeNull();
  });
});
