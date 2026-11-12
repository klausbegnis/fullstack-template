import { http, HttpResponse } from "msw";
import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionKeeper } from "@/features/auth/containers/session-keeper";
import { renderWithProviders } from "@/testing/render";
import { server } from "@/testing/msw/server";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
}));

const TTL_MS = 20_000;

function serveRefresh(respond: () => Response): { calls: number } {
  const counter = { calls: 0 };
  server.use(
    http.post("*/auth/refresh", () => {
      counter.calls += 1;
      return respond();
    }),
  );
  return counter;
}

function renewedForTtl() {
  return HttpResponse.json({
    access_expires_at: new Date(Date.now() + TTL_MS).toISOString(),
    session_expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  });
}

function refused() {
  return HttpResponse.json(
    { success: false, error: { code: "unauthorized", message: "Authentication required" } },
    { status: 401 },
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(Math, "random").mockReturnValue(0.5);
  replace.mockReset();
  document.cookie = "app_csrf=csrf-1; path=/";
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("SessionKeeper", () => {
  it("refreshes ahead of expiry and keeps refreshing from each new expiry", async () => {
    const refresh = serveRefresh(renewedForTtl);
    renderWithProviders(<SessionKeeper accessExpiresAt={Date.now() + TTL_MS} />);

    await act(() => vi.advanceTimersByTimeAsync(7_000));
    expect(refresh.calls).toBe(0);

    await act(() => vi.advanceTimersByTimeAsync(6_000));
    expect(refresh.calls).toBe(1);

    await act(() => vi.advanceTimersByTimeAsync(13_000));
    expect(refresh.calls).toBe(2);
    expect(replace).not.toHaveBeenCalled();
  });

  it("refreshes at once when the tab becomes visible near expiry", async () => {
    const refresh = serveRefresh(renewedForTtl);
    renderWithProviders(<SessionKeeper accessExpiresAt={Date.now() + 60_000} />);

    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    await vi.waitFor(() => expect(refresh.calls).toBe(1));
  });

  it("does not refresh on focus while expiry is still far away", async () => {
    const refresh = serveRefresh(renewedForTtl);
    renderWithProviders(<SessionKeeper accessExpiresAt={Date.now() + 900_000} />);

    act(() => {
      window.dispatchEvent(new Event("focus"));
    });
    await act(() => vi.advanceTimersByTimeAsync(1_000));

    expect(refresh.calls).toBe(0);
  });

  it("sends the visitor to the login page with the expired notice when the session ended", async () => {
    serveRefresh(refused);
    renderWithProviders(<SessionKeeper accessExpiresAt={Date.now() - 1_000} />);

    await act(() => vi.advanceTimersByTimeAsync(1_500));

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2F&reason=expired"));
  });

  it("follows another tab that announced the session ended", async () => {
    renderWithProviders(<SessionKeeper accessExpiresAt={Date.now() + 900_000} />);
    const otherTab = new BroadcastChannel("auth");

    otherTab.postMessage({ type: "logged-out" });

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/login?next=%2F&reason=expired"));
    otherTab.close();
  });
});
