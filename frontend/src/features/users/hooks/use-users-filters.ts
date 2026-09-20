import { useState } from "react";
import { DEFAULT_USER_FILTERS } from "@/features/users/model/user-filters";
import type { UserFilters } from "@/features/users/model/user-filters";

export interface UsersFiltersController {
  filters: UserFilters;
  goToPage: (page: number) => void;
  canGoToPreviousPage: boolean;
  canGoToNextPage: (totalPages: number) => boolean;
}

/**
 * Holds the users list's pagination state. A hook rather than a bare
 * `useState` in the container because it also derives the previous/next
 * button guards from that state — real composition, not a `useQuery` wrapper.
 */
export function useUsersFilters(
  initial: UserFilters = DEFAULT_USER_FILTERS,
): UsersFiltersController {
  const [filters, setFilters] = useState<UserFilters>(initial);

  return {
    filters,
    goToPage: (page: number) => {
      setFilters((current) => ({ ...current, page: Math.max(1, page) }));
    },
    canGoToPreviousPage: filters.page > 1,
    canGoToNextPage: (totalPages: number) => filters.page < totalPages,
  };
}
