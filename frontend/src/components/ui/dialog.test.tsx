import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/dialog";

describe("Dialog", () => {
  it("names the modal and exposes its content and close action", () => {
    render(
      <Dialog
        title="Edit item"
        description="Changes apply immediately."
        dialogRef={createRef()}
        onClose={vi.fn()}
        bodyClassName="p-3 sm:p-4 min-h-0"
      >
        Review the details.
      </Dialog>,
    );
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("aria-label", "Edit item");
    expect(screen.getByText("Changes apply immediately.")).toBeInTheDocument();
    expect(screen.getByText("Review the details.")).toHaveClass("p-3", "sm:p-4", "min-h-0");
    expect(screen.getByText("Review the details.")).not.toHaveClass("p-5");
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveClass("p-3", "min-h-0");
    expect(screen.getByRole("button", { hidden: true })).toHaveAttribute("aria-label", "Close");
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAccessibleDescription(
      "Changes apply immediately.",
    );
  });

  it("calls onClose from the close button", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog title="Edit item" dialogRef={createRef()} onClose={onClose} className="block">
        Body
      </Dialog>,
    );

    await user.click(screen.getByRole("button", { name: "Close", hidden: true }));

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("omits the header when asked to", () => {
    render(
      <Dialog title="Edit item" dialogRef={createRef()} onClose={vi.fn()} showHeader={false}>
        Body
      </Dialog>,
    );

    expect(screen.queryByRole("heading", { hidden: true })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { hidden: true })).not.toBeInTheDocument();
  });
});
