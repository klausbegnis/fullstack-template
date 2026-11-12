import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressBar } from "@/components/ui/progress-bar";

describe("ProgressBar", () => {
  it("reports the value against the maximum under its label", () => {
    render(<ProgressBar value={1} max={4} label="1 of 4 done" />);

    const bar = screen.getByRole("progressbar", { name: "1 of 4 done" });
    expect(bar).toHaveAttribute("value", "1");
    expect(bar).toHaveAttribute("max", "4");
  });

  it("keeps a positive maximum when there is nothing to count", () => {
    render(<ProgressBar value={0} max={0} label="0 of 0 done" />);

    expect(screen.getByRole("progressbar")).toHaveAttribute("max", "1");
  });
});
