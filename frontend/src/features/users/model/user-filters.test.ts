import { describe, expect, it } from "vitest";
import { DEFAULT_USER_FILTERS } from "@/features/users/model/user-filters";

describe("DEFAULT_USER_FILTERS", () => {
  it("starts on the first page with the backend's default page size", () => {
    expect(DEFAULT_USER_FILTERS).toEqual({ page: 1, pageSize: 20 });
  });
});
