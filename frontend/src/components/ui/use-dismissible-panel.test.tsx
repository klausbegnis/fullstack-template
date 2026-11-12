import { useRef, useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useDismissiblePanel } from "@/components/ui/use-dismissible-panel";

function PanelHarness({ open, onDismiss }: { open: boolean; onDismiss: () => void }) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useDismissiblePanel(open, onDismiss, triggerRef);
  return (
    <div>
      <button ref={triggerRef} type="button">
        Open panel
      </button>
      <input aria-label="Outside" />
      <aside ref={panelRef} tabIndex={-1} aria-label="Panel" hidden={!open}>
        <button type="button">Inside</button>
      </aside>
    </div>
  );
}

function TooltipHarness({ onDismiss }: { onDismiss: () => void }) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useDismissiblePanel(true, onDismiss, triggerRef, { moveFocus: false });
  return (
    <div>
      <button ref={triggerRef} type="button">
        Show hint
      </button>
      <span ref={panelRef} role="tooltip">
        Hint
      </span>
    </div>
  );
}

function SelfClosingHarness() {
  const [open, setOpen] = useState(true);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useDismissiblePanel(open, () => setOpen(false), triggerRef);
  return (
    <div>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>
        Open panel
      </button>
      <p>Outside text</p>
      <aside ref={panelRef} tabIndex={-1} aria-label="Panel" hidden={!open}>
        <button type="button">Inside</button>
      </aside>
    </div>
  );
}

function mountPanel(open: boolean) {
  const onDismiss = vi.fn();
  const view = render(<PanelHarness open={open} onDismiss={onDismiss} />);
  const reopen = (next: boolean) =>
    view.rerender(<PanelHarness open={next} onDismiss={onDismiss} />);
  return { onDismiss, reopen };
}

describe("useDismissiblePanel", () => {
  it("moves focus into the panel when it opens", () => {
    const { reopen } = mountPanel(false);
    reopen(true);
    expect(screen.getByRole("complementary", { name: "Panel" })).toHaveFocus();
  });

  it("dismisses on Escape, stops the key and gives focus back to the trigger", async () => {
    const user = userEvent.setup();
    const { onDismiss, reopen } = mountPanel(true);
    const panel = screen.getByRole("complementary", { name: "Panel" });
    const prevented: boolean[] = [];
    const recordPrevented = (event: KeyboardEvent) => prevented.push(event.defaultPrevented);
    const bubbled = vi.fn();
    document.addEventListener("keydown", recordPrevented, true);
    panel.addEventListener("keydown", bubbled);

    await user.keyboard("{Escape}");
    document.removeEventListener("keydown", recordPrevented, true);

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(prevented).toEqual([true]);
    expect(bubbled).not.toHaveBeenCalled();
    reopen(false);
    expect(screen.getByRole("button", { name: "Open panel" })).toHaveFocus();
  });

  it("dismisses on a pointer outside the panel and the trigger only", async () => {
    const user = userEvent.setup();
    const { onDismiss } = mountPanel(true);

    await user.click(screen.getByRole("button", { name: "Inside" }));
    await user.click(screen.getByRole("button", { name: "Open panel" }));
    expect(onDismiss).not.toHaveBeenCalled();
    await user.click(screen.getByRole("textbox", { name: "Outside" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("gives focus back to the trigger after a pointer on an area outside that cannot take focus", async () => {
    const user = userEvent.setup();
    render(<SelfClosingHarness />);
    await user.click(screen.getByRole("button", { name: "Inside" }));

    await user.click(screen.getByText("Outside text"));

    await waitFor(() => expect(screen.getByRole("button", { name: "Open panel" })).toHaveFocus());
  });

  it("leaves focus where the user moved it outside the panel", async () => {
    const user = userEvent.setup();
    const { reopen } = mountPanel(true);
    const outside = screen.getByRole("textbox", { name: "Outside" });

    await user.click(outside);
    reopen(false);
    expect(outside).toHaveFocus();
  });

  it("leaves focus on the trigger when told not to move it and still dismisses on Escape", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<TooltipHarness onDismiss={onDismiss} />);
    const trigger = screen.getByRole("button", { name: "Show hint" });
    trigger.focus();

    await user.keyboard("{Escape}");

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(trigger).toHaveFocus();
  });

  it("listens to nothing while closed", async () => {
    const user = userEvent.setup();
    const { onDismiss } = mountPanel(false);

    await user.click(screen.getByRole("textbox", { name: "Outside" }));
    await user.keyboard("{Escape}");
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
