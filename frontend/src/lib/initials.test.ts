import { describe, expect, it } from "vitest";
import { initialsOf } from "@/lib/initials";

describe("initialsOf", () => {
  it.each([
    ["Ada Lovelace (admin)", "AL"],
    ["Émile", "ÉM"],
    ["grace", "GR"],
    ["  Mary   Ann  Smith ", "MS"],
    ["", "?"],
  ])("initials of %s are %s", (name, initials) => {
    expect(initialsOf(name)).toBe(initials);
  });
});
