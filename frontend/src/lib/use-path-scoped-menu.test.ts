import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { usePathScopedMenu } from "@/lib/use-path-scoped-menu";

function renderMenu(initialPath: string | null) {
  return renderHook(({ pathname }) => usePathScopedMenu(pathname), {
    initialProps: { pathname: initialPath },
  });
}

describe("usePathScopedMenu", () => {
  it("starts closed and toggles open and closed on the same path", () => {
    const { result } = renderMenu("/users");
    expect(result.current.expanded).toBe(false);

    act(() => result.current.toggle());
    expect(result.current.expanded).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.expanded).toBe(false);
  });

  it("closes on request and stays closed", () => {
    const { result } = renderMenu("/users");
    act(() => result.current.toggle());

    act(() => result.current.close());
    act(() => result.current.close());

    expect(result.current.expanded).toBe(false);
  });

  it("closes once the path changes", () => {
    const { result, rerender } = renderMenu("/users");
    act(() => result.current.toggle());

    rerender({ pathname: "/users/new" });

    expect(result.current.expanded).toBe(false);
  });

  it("stays closed when the user comes back to the path it was opened on", () => {
    const { result, rerender } = renderMenu("/users");
    act(() => result.current.toggle());

    rerender({ pathname: "/users/new" });
    rerender({ pathname: "/users" });

    expect(result.current.expanded).toBe(false);
  });

  it("opens again on the new path after a navigation closed it", () => {
    const { result, rerender } = renderMenu("/users");
    act(() => result.current.toggle());
    rerender({ pathname: "/users/new" });

    act(() => result.current.toggle());

    expect(result.current.expanded).toBe(true);
  });
});
