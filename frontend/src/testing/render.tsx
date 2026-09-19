import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

/**
 * Builds a provider wrapper around a fresh, retry-free `QueryClient`. Each
 * call returns its own client so parallel tests never share a cache.
 */
export function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

/**
 * Renders a client component wrapped with the same providers the app
 * supplies at runtime, using a fresh `QueryClient` per call.
 */
export function renderWithProviders(ui: ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}
