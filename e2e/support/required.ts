/** Returns a value the test needs, failing with the name of what is missing instead of guessing a default. */
export function required<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined) {
    throw new Error(`Expected ${what}, but it is missing.`);
  }
  return value;
}
