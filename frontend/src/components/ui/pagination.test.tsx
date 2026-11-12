import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "@/components/ui/pagination";

function showPager(page: number, totalItems = 48, onPageChange = vi.fn()) {
  render(
    <Pagination
      page={page}
      pageCount={Math.ceil(totalItems / 10)}
      totalItems={totalItems}
      pageSize={10}
      onPageChange={onPageChange}
    />,
  );
  return onPageChange;
}

describe("Pagination", () => {
  it("renders nothing while every row fits on one page", () => {
    showPager(1, 10);
    expect(screen.queryByRole("navigation", { name: "Pagination" })).not.toBeInTheDocument();
  });

  it("shows the visible range, the current page and both phone and desktop page labels", () => {
    showPager(2);
    const nav = screen.getByRole("navigation", { name: "Pagination" });
    expect(nav).toHaveTextContent("Showing 11–20 of 48 items");
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Page 1" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("Page 2 of 5")).toBeInTheDocument();
  });

  it("fills only the current page with the brand color", () => {
    showPager(2);
    const current = screen.getByRole("button", { name: "Page 2" });
    expect(current).toHaveClass("bg-brand", "text-white");
    expect(current).not.toHaveClass("bg-white");
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveClass("bg-white");
  });

  it("disables Previous on the first page", () => {
    showPager(1);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("disables Next on the last page", () => {
    showPager(5);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
  });

  it("asks for the neighbouring or chosen page", async () => {
    const user = userEvent.setup();
    const onPageChange = showPager(2);

    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Previous" }));
    await user.click(screen.getByRole("button", { name: "Page 4" }));

    expect(onPageChange.mock.calls).toEqual([[3], [1], [4]]);
  });

  it("truncates a long page strip and names the item kind", () => {
    render(
      <Pagination
        page={6}
        pageCount={12}
        totalItems={118}
        pageSize={10}
        itemLabel="users"
        label="Users pagination"
        onPageChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("navigation", { name: "Users pagination" })).toHaveTextContent(
      "Showing 51–60 of 118 users",
    );
    expect(screen.queryByRole("button", { name: "Page 3" })).not.toBeInTheDocument();
    expect(screen.getAllByText("…")).toHaveLength(2);
  });
});
