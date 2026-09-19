import { renderHook, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useUsersFilters } from "@/features/users/hooks/use-users-filters";

describe("useUsersFilters", () => {
  it("starts on page 1 and disallows going to the previous page", () => {
    const { result } = renderHook(() => useUsersFilters());

    expect(result.current.filters.page).toBe(1);
    expect(result.current.canGoToPreviousPage).toBe(false);
    expect(result.current.canGoToNextPage(3)).toBe(true);
  });

  it("moves to the requested page and updates the derived guards", () => {
    const { result } = renderHook(() => useUsersFilters());

    act(() => {
      result.current.goToPage(2);
    });

    expect(result.current.filters.page).toBe(2);
    expect(result.current.canGoToPreviousPage).toBe(true);
    expect(result.current.canGoToNextPage(2)).toBe(false);
  });

  it("never goes below page 1", () => {
    const { result } = renderHook(() => useUsersFilters());

    act(() => {
      result.current.goToPage(0);
    });

    expect(result.current.filters.page).toBe(1);
  });
});
