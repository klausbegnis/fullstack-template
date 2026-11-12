import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Pagination } from "@/components/ui/pagination";
import { usePagination } from "@/components/ui/use-pagination";

function rows(count: number) {
  return Array.from({ length: count }, (_, index) => `Row ${index + 1}`);
}

function Harness({ items, resetKey }: { items: readonly string[]; resetKey: string }) {
  const pager = usePagination(items, resetKey, { anchorId: "harness-title" });
  return (
    <section>
      <h2 id="harness-title">List</h2>
      <ul aria-label="Rows">
        {pager.pageItems.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <Pagination {...pager.pagerProps} />
    </section>
  );
}

function visibleRows() {
  return within(screen.getByRole("list", { name: "Rows" }))
    .getAllByRole("listitem")
    .map((item) => item.textContent);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("usePagination", () => {
  it("shows the first ten rows and moves to the chosen page", async () => {
    const user = userEvent.setup();
    render(<Harness items={rows(23)} resetKey="" />);
    expect(visibleRows()).toHaveLength(10);

    await user.click(screen.getByRole("button", { name: "Page 3" }));

    expect(screen.getByText("Row 21")).toBeInTheDocument();
    expect(screen.queryByText("Row 20")).not.toBeInTheDocument();
  });

  it("returns to the first page when the reset key changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness items={rows(23)} resetKey="a" />);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Row 11")).toBeInTheDocument();

    rerender(<Harness items={rows(23)} resetKey="b" />);

    expect(screen.getByText("Row 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
  });

  it("stays on the first page when the reset key returns to an earlier value", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness items={rows(23)} resetKey="" />);
    await user.click(screen.getByRole("button", { name: "Page 3" }));

    rerender(<Harness items={rows(23)} resetKey="search" />);
    rerender(<Harness items={rows(23)} resetKey="" />);

    expect(screen.getByText("Row 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
  });

  it("clamps to the new last page when the list shrinks", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Harness items={rows(31)} resetKey="" />);
    await user.click(screen.getByRole("button", { name: "Page 4" }));
    expect(visibleRows()).toEqual(["Row 31"]);

    rerender(<Harness items={rows(30)} resetKey="" />);

    expect(screen.getByText("Row 21")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 3" })).toHaveAttribute("aria-current", "page");
  });

  it("scrolls the heading into view and keeps focus in the pager at the last page", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    render(<Harness items={rows(15)} resetKey="" />);

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
    expect(scrollIntoView.mock.contexts[0]).toBe(screen.getByRole("heading", { name: "List" }));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveFocus();
  });
});
