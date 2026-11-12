"use client";

import type { Ref } from "react";
import { cn } from "@/lib/cn";
import { pageRange, pageWindow } from "@/components/ui/pagination-window";

export interface PaginationProps {
  page: number;
  pageCount: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  itemLabel?: string;
  label?: string;
  navRef?: Ref<HTMLElement>;
  className?: string;
}

const CONTROL_CLASSES =
  "inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border px-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed";

const IDLE_CLASSES =
  "border-gray-200 bg-white text-gray-900 hover:bg-gray-50 disabled:text-gray-400 disabled:hover:bg-white";

const CURRENT_CLASSES = "border-brand bg-brand text-white";

/**
 * The shared pager under a growing table or list: "Showing 1–10 of N items" with Previous, the
 * page numbers and Next, or "Page X of Y" instead of the numbers below `md`. It renders nothing
 * while every row fits on one page. It is a client component: its buttons call `onPageChange`.
 */
export function Pagination({
  page,
  pageCount,
  totalItems,
  pageSize,
  onPageChange,
  itemLabel = "items",
  label = "Pagination",
  navRef,
  className,
}: PaginationProps) {
  if (totalItems <= pageSize) return null;
  const { from, to } = pageRange(page, pageSize, totalItems);
  return (
    <nav
      ref={navRef}
      aria-label={label}
      className={cn("flex flex-wrap items-center justify-between gap-3", className)}
    >
      <p aria-live="polite" className="text-[13px] text-gray-500">
        {`Showing ${from}–${to} of ${totalItems} ${itemLabel}`}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={cn(CONTROL_CLASSES, IDLE_CLASSES)}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <ul className="hidden items-center gap-1 md:flex">
          {pageWindow(page, pageCount).map((slot) =>
            slot.kind === "gap" ? (
              <li key={slot.key} aria-hidden="true" className="px-1 text-sm text-gray-500">
                …
              </li>
            ) : (
              <li key={slot.page}>
                <button
                  type="button"
                  aria-label={`Page ${slot.page}`}
                  aria-current={slot.page === page ? "page" : undefined}
                  className={cn(
                    CONTROL_CLASSES,
                    slot.page === page ? CURRENT_CLASSES : IDLE_CLASSES,
                  )}
                  onClick={() => onPageChange(slot.page)}
                >
                  {slot.page}
                </button>
              </li>
            ),
          )}
        </ul>
        <p className="text-sm font-semibold text-gray-900 md:hidden">{`Page ${page} of ${pageCount}`}</p>
        <button
          type="button"
          className={cn(CONTROL_CLASSES, IDLE_CLASSES)}
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
