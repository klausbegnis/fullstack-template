import { describe, expect, it } from "vitest";
import {
  PAGE_SIZE,
  clampPage,
  countPages,
  pageRange,
  pageWindow,
} from "@/components/ui/pagination-window";

function pages(page: number, pageCount: number) {
  return pageWindow(page, pageCount).map((slot) => (slot.kind === "page" ? slot.page : "…"));
}

describe("pagination window", () => {
  it("pages ten rows at a time and never reports zero pages", () => {
    expect(PAGE_SIZE).toBe(10);
    expect(countPages(0)).toBe(1);
    expect(countPages(10)).toBe(1);
    expect(countPages(11)).toBe(2);
    expect(countPages(48)).toBe(5);
  });

  it("clamps a page into the existing pages", () => {
    expect(clampPage(0, 3)).toBe(1);
    expect(clampPage(5, 3)).toBe(3);
    expect(clampPage(2, 0)).toBe(1);
  });

  it("reports the rows a page shows", () => {
    expect(pageRange(2, 10, 48)).toEqual({ from: 11, to: 20 });
    expect(pageRange(5, 10, 48)).toEqual({ from: 41, to: 48 });
    expect(pageRange(1, 10, 0)).toEqual({ from: 0, to: 0 });
  });

  it("lists every page up to seven", () => {
    expect(pages(3, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("keeps the first, last and current pages with gaps beyond seven", () => {
    expect(pages(1, 12)).toEqual([1, 2, "…", 12]);
    expect(pages(6, 12)).toEqual([1, "…", 5, 6, 7, "…", 12]);
    expect(pages(12, 12)).toEqual([1, "…", 11, 12]);
    expect(pages(3, 12)).toEqual([1, 2, 3, 4, "…", 12]);
  });
});
