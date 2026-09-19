import { describe, expect, it } from "vitest";
import { nextId } from "@/testing/factories";

describe("nextId", () => {
  it("returns a unique id on each call", () => {
    expect(nextId()).not.toBe(nextId());
  });
});
