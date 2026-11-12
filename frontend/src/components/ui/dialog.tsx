"use client";

import { useId } from "react";
import type { ReactNode, RefObject } from "react";
import { cn } from "@/lib/cn";

export interface DialogProps {
  title: string;
  titleIcon?: ReactNode;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  dialogRef: RefObject<HTMLDialogElement | null>;
  className?: string;
  bodyClassName?: string;
  showHeader?: boolean;
}

/**
 * Presents a native `<dialog>` with a titled header, a named close button and responsive content.
 * It never opens itself: the caller passes the ref returned by `useModalDialog`, which shows it
 * modally and routes Escape, the native cancel and a backdrop click to `onClose`.
 */
export function Dialog({
  title,
  titleIcon,
  description,
  children,
  onClose,
  dialogRef,
  className,
  bodyClassName,
  showHeader = true,
}: DialogProps) {
  const descriptionId = useId();
  const describedBy = showHeader && description ? descriptionId : undefined;
  return (
    <dialog
      ref={dialogRef}
      tabIndex={-1}
      aria-label={title}
      aria-describedby={describedBy}
      className={cn(
        "text-gray-900 backdrop:bg-gray-950/40",
        className ??
          "m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-3xl overflow-y-auto rounded-2xl border border-gray-200 bg-white p-0 shadow-2xl",
      )}
    >
      {showHeader ? (
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-gray-200 bg-white px-5 py-4 sm:px-6">
          <div>
            <h2 className="flex items-center gap-3 text-xl font-semibold tracking-tight">
              {titleIcon}
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="mt-1 text-sm text-gray-500">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-11 flex-none place-items-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-brand"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="size-5"
              aria-hidden="true"
            >
              <path d="m6 6 12 12M6 18 18 6" />
            </svg>
          </button>
        </header>
      ) : null}
      <div className={bodyClassName ?? "p-5 sm:p-6"}>{children}</div>
    </dialog>
  );
}
