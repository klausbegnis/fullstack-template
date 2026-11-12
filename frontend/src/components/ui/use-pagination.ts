"use client";

import { useRef, useState, type RefObject } from "react";
import { flushSync } from "react-dom";
import { PAGE_SIZE, clampPage, countPages } from "@/components/ui/pagination-window";
import type { PaginationProps } from "@/components/ui/pagination";

interface UsePaginationOptions {
  pageSize?: number;
  anchorId?: string;
}

type PagerProps = Pick<
  PaginationProps,
  "page" | "pageCount" | "totalItems" | "pageSize" | "onPageChange" | "navRef"
>;

interface PaginationController<T> {
  pageItems: readonly T[];
  totalItems: number;
  pagerProps: PagerProps;
}

/**
 * Holds a page number that returns to 1 whenever `resetKey` changes (a new search, filter or tab),
 * stored during render instead of reset in an effect, so returning to an earlier key stays on page 1.
 */
export function usePageState(resetKey: string): [number, (page: number) => void] {
  const [state, setState] = useState({ key: resetKey, page: 1 });
  if (state.key !== resetKey) setState({ key: resetKey, page: 1 });
  const page = state.key === resetKey ? state.page : 1;
  return [page, (next: number) => setState({ key: resetKey, page: next })];
}

function isUsable(element: Element | null, nav: HTMLElement): boolean {
  return (
    element instanceof HTMLElement &&
    nav.contains(element) &&
    !(element instanceof HTMLButtonElement && element.disabled)
  );
}

function keepFocusInPager(nav: HTMLElement) {
  if (isUsable(document.activeElement, nav)) return;
  const candidates = [
    nav.querySelector<HTMLButtonElement>('[aria-current="page"]'),
    ...nav.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
  ];
  for (const candidate of candidates) {
    candidate?.focus();
    if (document.activeElement === candidate) return;
  }
}

function settleAfterPageChange(
  navRef: RefObject<HTMLElement | null>,
  anchorId: string | undefined,
  hadFocus: boolean,
) {
  if (anchorId) document.getElementById(anchorId)?.scrollIntoView?.({ block: "nearest" });
  if (hadFocus && navRef.current) keepFocusInPager(navRef.current);
}

/**
 * Wraps a page setter for the shared `Pagination`: the new page renders synchronously, then the
 * `anchorId` element (the table's heading) scrolls into view instead of the document top and focus
 * stays inside the pager when the pressed button becomes disabled. Server-paged lists pair it with
 * `placeholderData: keepPreviousData`, so the pager stays mounted while the next page loads.
 */
export function usePagerControl(
  onPageChange: (page: number) => void,
  anchorId?: string,
): Pick<PagerProps, "onPageChange" | "navRef"> {
  const navRef = useRef<HTMLElement>(null);
  return {
    navRef,
    onPageChange: (next: number) => {
      const nav = navRef.current;
      const hadFocus = nav !== null && nav.contains(document.activeElement);
      flushSync(() => onPageChange(next));
      settleAfterPageChange(navRef, anchorId, hadFocus);
    },
  };
}

/**
 * Slices an already-loaded list into pages of ten for the shared `Pagination`. Filters and search
 * apply to `items` before it arrives here; the page returns to 1 when `resetKey` changes and
 * clamps to the last page when the list shrinks. Page changes settle through `usePagerControl`.
 */
export function usePagination<T>(
  items: readonly T[],
  resetKey: string,
  options: UsePaginationOptions = {},
): PaginationController<T> {
  const pageSize = options.pageSize ?? PAGE_SIZE;
  const [requested, setRequested] = usePageState(resetKey);
  const pageCount = countPages(items.length, pageSize);
  const page = clampPage(requested, pageCount);
  const control = usePagerControl(
    (next) => setRequested(clampPage(next, pageCount)),
    options.anchorId,
  );
  return {
    pageItems: items.slice((page - 1) * pageSize, page * pageSize),
    totalItems: items.length,
    pagerProps: { page, pageCount, totalItems: items.length, pageSize, ...control },
  };
}
