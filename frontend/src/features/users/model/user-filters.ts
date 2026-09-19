export interface UserFilters {
  page: number;
  pageSize: number;
}

export const DEFAULT_USER_FILTERS: UserFilters = { page: 1, pageSize: 20 };
