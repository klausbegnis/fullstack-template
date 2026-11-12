import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState", () => {
  it("names the absence and explains it", () => {
    render(<EmptyState title="No items yet" description="Items you create show up here." />);

    expect(screen.getByRole("heading", { level: 2, name: "No items yet" })).toBeInTheDocument();
    expect(screen.getByText("Items you create show up here.")).toBeInTheDocument();
  });

  it("renders the eyebrow and the action when given", () => {
    render(
      <EmptyState
        eyebrow="Getting started"
        title="No items yet"
        description="Items you create show up here."
        action={<a href="/items/new">New item</a>}
      />,
    );

    expect(screen.getByText("Getting started")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New item" })).toHaveAttribute("href", "/items/new");
  });
});
