import { useState } from "react";
import { DEFAULT_USER_FILTERS } from "@/features/users/model/user-filters";
import type { UserFilters } from "@/features/users/model/user-filters";

export interface UsersFiltersController {
  filters: UserFilters;
  goToPage: (page: number) => void;
}

/**
 * Holds the users list's filter and pagination state, so the query key and
 * the pager read one value. A page below 1 is clamped to the first page; the
 * upper bound is the pager's, which only offers existing pages.
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
  };
}
