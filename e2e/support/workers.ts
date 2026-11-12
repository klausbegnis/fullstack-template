import { availableParallelism, loadavg } from "node:os";

/**
 * Busy cores one Playwright worker costs across its browser and the stack's Next, api and
 * Postgres (about 2 when measured with two workers on one stack).
 */
export const CORES_PER_WORKER = 2;

/** Where the run's worker count came from, printed once when the config loads. */
export type WorkerSource = "env" | "CI" | "load-aware";

/** The worker count for this run and its source. */
export interface WorkerChoice {
  workers: number;
  source: WorkerSource;
}

/**
 * Playwright worker count for a run without `E2E_WORKERS`: the cores the 1-minute load leaves
 * free over `CORES_PER_WORKER`, capped at half the cores, never below 1. Playwright's
 * half-the-cores default ignores host load and pushes specs past their timeouts on a busy host.
 */
export function loadAwareWorkers(): number {
  const cores = availableParallelism();
  const [oneMinuteLoad = 0] = loadavg();
  const byHeadroom = Math.floor((cores - oneMinuteLoad) / CORES_PER_WORKER);
  return Math.max(1, Math.min(Math.floor(cores / 2), byHeadroom));
}

/** `E2E_WORKERS` when set, 2 on CI, else the load-aware count. */
export function chooseWorkers(): WorkerChoice {
  if (process.env.E2E_WORKERS) {
    return { workers: Number(process.env.E2E_WORKERS), source: "env" };
  }
  if (process.env.CI) {
    return { workers: 2, source: "CI" };
  }
  return { workers: loadAwareWorkers(), source: "load-aware" };
}
