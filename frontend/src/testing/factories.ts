let sequence = 0;

/**
 * Returns a monotonically increasing id, useful for building test fixtures
 * whose identity does not matter beyond uniqueness.
 */
export function nextId(): string {
  sequence += 1;
  return `test-${sequence}`;
}
