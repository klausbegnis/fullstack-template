/** How many rows a growing table or list shows per page. */
export const PAGE_SIZE = 10;

/** One slot of the page-number strip: a page button, or the ellipsis between two runs. */
export type PageWindowSlot = { kind: "page"; page: number } | { kind: "gap"; key: string };

const FULL_STRIP_LIMIT = 7;

/** The number of pages a list of `totalItems` needs, never less than one. */
export function countPages(totalItems: number, pageSize: number = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(totalItems / pageSize));
}

/** Keeps a page inside `1..pageCount`, so a list that shrank lands on its new last page. */
export function clampPage(page: number, pageCount: number): number {
  return Math.min(Math.max(1, Math.trunc(page)), Math.max(1, pageCount));
}

/** The 1-based positions of the first and last row a page shows. */
export function pageRange(
  page: number,
  pageSize: number,
  totalItems: number,
): { from: number; to: number } {
  if (totalItems === 0) return { from: 0, to: 0 };
  return { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, totalItems) };
}

/**
 * The page-number strip: every page up to seven, otherwise the first, the last and the current
 * page with its neighbours, with a gap where pages are skipped.
 */
export function pageWindow(page: number, pageCount: number): PageWindowSlot[] {
  if (pageCount <= FULL_STRIP_LIMIT) {
    return Array.from({ length: pageCount }, (_, index) => ({ kind: "page", page: index + 1 }));
  }
  const start = Math.max(2, page - 1);
  const end = Math.min(pageCount - 1, page + 1);
  const slots: PageWindowSlot[] = [{ kind: "page", page: 1 }];
  if (start > 2) slots.push({ kind: "gap", key: "gap-start" });
  for (let current = start; current <= end; current += 1) {
    slots.push({ kind: "page", page: current });
  }
  if (end < pageCount - 1) slots.push({ kind: "gap", key: "gap-end" });
  slots.push({ kind: "page", page: pageCount });
  return slots;
}
