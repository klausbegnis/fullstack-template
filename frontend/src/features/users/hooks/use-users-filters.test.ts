import { renderHook, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useUsersFilters } from "@/features/users/hooks/use-users-filters";

describe("useUsersFilters", () => {
  it("starts on page 1 with the default page size", () => {
    const { result } = renderHook(() => useUsersFilters());

    expect(result.current.filters).toEqual({ page: 1, pageSize: 20 });
  });

  it("moves to the requested page", () => {
    const { result } = renderHook(() => useUsersFilters());

    act(() => {
      result.current.goToPage(2);
    });

    expect(result.current.filters.page).toBe(2);
  });

  it("never goes below page 1", () => {
    const { result } = renderHook(() => useUsersFilters());

    act(() => {
      result.current.goToPage(0);
    });

    expect(result.current.filters.page).toBe(1);
  });
});
