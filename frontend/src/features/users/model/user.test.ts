import { describe, expect, it } from "vitest";
import { displayNameOf } from "@/features/users/model/user";

describe("displayNameOf", () => {
  it("returns the user's name when there is one", () => {
    expect(displayNameOf({ name: "Ada Lovelace", email: "ada@example.com" })).toBe("Ada Lovelace");
  });

  it("falls back to the email's local part when the name is blank", () => {
    expect(displayNameOf({ name: "  ", email: "root@example.com" })).toBe("root");
  });
});
