import { QueryClient, defaultShouldDehydrateQuery, isServer } from "@tanstack/react-query";
import { cache } from "react";
import { ApiError } from "@/lib/errors/api-error";

const MAX_QUERY_RETRIES = 3;
const CLIENT_ERROR_MIN = 400;
const CLIENT_ERROR_MAX = 499;

/**
 * Retries a failed query up to three times, except when the API answered with
 * a 4xx: a refused or missing resource does not fix itself, and retrying it
 * only delays the error the page shows.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (
    error instanceof ApiError &&
    error.status >= CLIENT_ERROR_MIN &&
    error.status <= CLIENT_ERROR_MAX
  ) {
    return false;
  }
  return failureCount < MAX_QUERY_RETRIES;
}

/**
 * Builds a `QueryClient` configured for this template: queries are treated
 * as fresh for a short window so a server-side prefetch is not immediately
 * refetched on hydration, 4xx answers are not retried, and pending queries are dehydrated alongside
 * successful ones so streaming SSR can resolve them on the client.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        retry: shouldRetryQuery,
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
