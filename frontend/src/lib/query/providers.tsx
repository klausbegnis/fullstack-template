"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { makeQueryClient } from "@/lib/query/query-client";

export interface ProvidersProps {
  children: ReactNode;
}

/**
 * Mounts the app-wide client providers. Kept to a single `useState`-held
 * `QueryClient` per browser tab so the cache survives route navigations
 * without being shared across unrelated requests.
 */
export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(makeQueryClient);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
