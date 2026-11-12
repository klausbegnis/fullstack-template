"use client";

import { useEffect, useEffectEvent, useRef, type RefObject } from "react";

/** How a modal opened through `useModalDialog` places focus when it opens and closes. */
export interface ModalDialogOptions {
  restoreFocusRef?: RefObject<HTMLElement | null>;
  initialFocus?: string;
}

function isOutside(dialog: HTMLDialogElement, event: PointerEvent) {
  const bounds = dialog.getBoundingClientRect();
  return (
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom
  );
}

function focusFirstControl(dialog: HTMLDialogElement) {
  const first =
    dialog.querySelector<HTMLElement>("[autofocus]") ??
    dialog.querySelector<HTMLElement>("input, textarea, select, button");
  (first ?? dialog).focus();
}

/**
 * The one way the app opens a modal: shows the native `<dialog>` modally while `open` is true and
 * calls `onClose` on Escape, on the native cancel and on a pointer on the backdrop outside the
 * dialog box. On open it focuses the first element matching `initialFocus` (or the dialog when
 * nothing matches); on close it returns focus to `restoreFocusRef` or to the element that had it
 * when the dialog opened. Whether a close is allowed stays with `onClose`.
 */
export function useModalDialog(
  open: boolean,
  onClose: () => void,
  { restoreFocusRef, initialFocus }: ModalDialogOptions = {},
) {
  const ref = useRef<HTMLDialogElement>(null);
  const requestClose = useEffectEvent(onClose);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = restoreFocusRef?.current ?? document.activeElement;
    if (!dialog.open) {
      const native = typeof dialog.showModal === "function";
      if (native) dialog.showModal();
      else dialog.setAttribute("open", "");
      if (initialFocus) (dialog.querySelector<HTMLElement>(initialFocus) ?? dialog).focus();
      else if (!native) focusFirstControl(dialog);
    }
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      requestClose();
    };
    const handleCancel = (event: Event) => {
      event.preventDefault();
      requestClose();
    };
    const handleOutside = (event: PointerEvent) => {
      if (event.target !== dialog || !isOutside(dialog, event)) return;
      event.preventDefault();
      requestClose();
    };
    dialog.addEventListener("pointerdown", handleOutside);
    dialog.addEventListener("keydown", handleKey);
    dialog.addEventListener("cancel", handleCancel);
    return () => {
      dialog.removeEventListener("pointerdown", handleOutside);
      dialog.removeEventListener("keydown", handleKey);
      dialog.removeEventListener("cancel", handleCancel);
      if (typeof dialog.close === "function" && dialog.open) dialog.close();
      else dialog.removeAttribute("open");
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, [open, restoreFocusRef, initialFocus]);
  return ref;
}
