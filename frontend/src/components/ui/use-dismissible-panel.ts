"use client";

import { useEffect, useEffectEvent, useRef, type RefObject } from "react";

/**
 * Moves focus into a non-modal panel while it is open, dismisses it on Escape or on a pointer
 * outside both the panel and its trigger, and gives focus back to the trigger when the panel
 * closes with focus inside it or lost to the page body, including when the closing pointer lands
 * on an area that cannot take focus. With `moveFocus: false` (a tooltip) focus is left alone: the
 * panel never takes it on open and the trigger never takes it back on close.
 */
export function useDismissiblePanel<T extends HTMLElement = HTMLElement>(
  open: boolean,
  onDismiss: () => void,
  triggerRef: RefObject<HTMLElement | null>,
  { moveFocus = true }: { moveFocus?: boolean } = {},
) {
  const ref = useRef<T>(null);
  const requestDismiss = useEffectEvent(onDismiss);
  useEffect(() => {
    const panel = ref.current;
    const trigger = triggerRef.current;
    if (!panel || !open) return;
    if (moveFocus) panel.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      requestDismiss();
    };
    const handleOutside = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (panel.contains(target) || trigger?.contains(target)) return;
      requestDismiss();
    };
    document.addEventListener("keydown", handleKey, true);
    document.addEventListener("pointerdown", handleOutside, true);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      document.removeEventListener("pointerdown", handleOutside, true);
      if (!moveFocus) return;
      const restoreLostFocus = () => {
        const active = document.activeElement;
        const focusLost = active === null || active === document.body || panel.contains(active);
        if (focusLost && trigger?.isConnected) trigger.focus();
      };
      restoreLostFocus();
      window.setTimeout(restoreLostFocus, 0);
    };
  }, [open, triggerRef, moveFocus]);
  return ref;
}
