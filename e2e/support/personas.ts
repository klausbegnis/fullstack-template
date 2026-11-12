import path from "node:path";

export const ROLES = ["admin", "member"] as const;
export type Role = (typeof ROLES)[number];

/** The password every user the seed or a spec creates signs in with; never a real secret. */
export const SEEDED_PASSWORD = "e2e-not-a-real-pw";

const AUTH_DIR = path.resolve(import.meta.dirname, "..", ".auth");

/** The seeded ids, names and credentials, written by `seed.setup.ts` and read by the `seed` fixture. */
export const SEED_FILE = path.join(AUTH_DIR, "seed.json");

/** Where the setup project stores the signed-in browser state of one role. */
export function storageStatePath(role: Role): string {
  return path.join(AUTH_DIR, `${role}.json`);
}
