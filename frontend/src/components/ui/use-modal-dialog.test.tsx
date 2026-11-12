import { useRef } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useModalDialog, type ModalDialogOptions } from "@/components/ui/use-modal-dialog";

function DialogHarness({
  open,
  onClose,
  initialFocus,
  restoreToOther = false,
}: {
  open: boolean;
  onClose: () => void;
  initialFocus?: ModalDialogOptions["initialFocus"];
  restoreToOther?: boolean;
}) {
  const otherRef = useRef<HTMLButtonElement>(null);
  const ref = useModalDialog(open, onClose, {
    initialFocus,
    restoreFocusRef: restoreToOther ? otherRef : undefined,
  });
  return (
    <div>
      <button type="button">Open</button>
      <button type="button" ref={otherRef}>
        Other
      </button>
      <dialog ref={ref} aria-label="Edit item" tabIndex={-1}>
        <input aria-label="Name" />
        <button type="button">Close</button>
      </dialog>
    </div>
  );
}

function pointerAt(clientX: number, clientY: number) {
  return new MouseEvent("pointerdown", { bubbles: true, cancelable: true, clientX, clientY });
}

function mountOpen(props: Partial<Parameters<typeof DialogHarness>[0]> = {}) {
  const onClose = vi.fn();
  const view = render(<DialogHarness open={false} onClose={onClose} {...props} />);
  const opener = screen.getByRole("button", { name: "Open" });
  act(() => opener.focus());
  const setOpen = (open: boolean) =>
    view.rerender(<DialogHarness open={open} onClose={onClose} {...props} />);
  setOpen(true);
  const dialog = screen.getByRole("dialog", { name: "Edit item" });
  vi.spyOn(dialog, "getBoundingClientRect").mockReturnValue(new DOMRect(100, 100, 200, 200));
  return { onClose, opener, dialog, setOpen };
}

describe("useModalDialog", () => {
  it("opens the native dialog, handles Escape and closes when state changes", async () => {
    const user = userEvent.setup();
    const { onClose, setOpen } = mountOpen();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
    setOpen(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on a backdrop pointerdown by default without letting the click move focus", () => {
    const { onClose, dialog } = mountOpen();
    const notPrevented = fireEvent(dialog, pointerAt(50, 50));
    expect(onClose).toHaveBeenCalledOnce();
    expect(notPrevented).toBe(false);
  });

  it("stays open on a pointerdown inside the dialog box", async () => {
    const user = userEvent.setup();
    const { onClose, dialog } = mountOpen();
    fireEvent(dialog, pointerAt(150, 150));
    await user.click(screen.getByRole("textbox", { name: "Name" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes through the same path on the native cancel event", () => {
    const { onClose, dialog } = mountOpen();
    const notPrevented = fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(notPrevented).toBe(false);
  });

  it("returns focus to the element that opened it", () => {
    const { opener, setOpen } = mountOpen();
    expect(opener).not.toHaveFocus();
    setOpen(false);
    expect(opener).toHaveFocus();
  });

  it("returns focus to restoreFocusRef when one is given", () => {
    const { setOpen } = mountOpen({ restoreToOther: true });
    setOpen(false);
    expect(screen.getByRole("button", { name: "Other" })).toHaveFocus();
  });

  it("focuses the first element matching initialFocus", () => {
    mountOpen({ initialFocus: "button" });
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });
});
