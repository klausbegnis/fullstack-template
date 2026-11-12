import { describe, expect, it } from "vitest";
import {
  isNearExpiry,
  MIN_REFRESH_DELAY_MS,
  refreshDelayMs,
} from "@/features/auth/model/refresh-schedule";

const NOW = 1_000_000;
const MIDPOINT = () => 0.5;
const LOWEST = () => 0;
const HIGHEST = () => 0.999_999;

describe("refreshDelayMs", () => {
  it("refreshes a 15-minute token two minutes before it expires", () => {
    expect(refreshDelayMs(NOW + 900_000, NOW, MIDPOINT)).toBe(780_000);
  });

  it("spreads the 15-minute refresh by at most 15 seconds either way", () => {
    expect(refreshDelayMs(NOW + 900_000, NOW, LOWEST)).toBe(765_000);
    expect(refreshDelayMs(NOW + 900_000, NOW, HIGHEST)).toBe(795_000);
  });

  it("refreshes a 20-second token about halfway instead of looping", () => {
    expect(refreshDelayMs(NOW + 20_000, NOW, MIDPOINT)).toBe(10_000);
    expect(refreshDelayMs(NOW + 20_000, NOW, LOWEST)).toBe(8_000);
    expect(refreshDelayMs(NOW + 20_000, NOW, HIGHEST)).toBe(12_000);
  });

  it("waits the floor for a token already past expiry", () => {
    expect(refreshDelayMs(NOW - 5_000, NOW, MIDPOINT)).toBe(MIN_REFRESH_DELAY_MS);
    expect(refreshDelayMs(NOW + 500, NOW, LOWEST)).toBe(MIN_REFRESH_DELAY_MS);
  });
});

describe("isNearExpiry", () => {
  it("is true inside the two-minute lead and past expiry, false before", () => {
    expect(isNearExpiry(NOW + 120_000, NOW)).toBe(true);
    expect(isNearExpiry(NOW - 1, NOW)).toBe(true);
    expect(isNearExpiry(NOW + 120_001, NOW)).toBe(false);
  });
});
