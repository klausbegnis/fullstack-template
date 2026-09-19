import { QueryClient, defaultShouldDehydrateQuery, isServer } from "@tanstack/react-query";
import { cache } from "react";

/**
 * Builds a `QueryClient` configured for this template: queries are treated
 * as fresh for a short window so a server-side prefetch is not immediately
 * refetched on hydration, and pending queries are dehydrated alongside
 * successful ones so streaming SSR can resolve them on the client.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
      },
      dehydrate: {
        shouldDehydrateQuery: (query) =>
          defaultShouldDehydrateQuery(query) || query.state.status === "pending",
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getBrowserQueryClient(): QueryClient {
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient();
  }
  return browserQueryClient;
}

/**
 * Returns the `QueryClient` for the current render. On the server this
 * creates a fresh client per request via React's `cache()`; in the browser
 * it returns a single module-level singleton so the cache survives
 * navigations.
 */
export const getQueryClient = cache((): QueryClient => {
  if (isServer) {
    return makeQueryClient();
  }
  return getBrowserQueryClient();
});
