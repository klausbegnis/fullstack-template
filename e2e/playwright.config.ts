import { defineConfig, devices } from "@playwright/test";
import { browserOriginHeaders, env } from "./support/env";
import { EXPECT_TIMEOUT_MS, TEST_TIMEOUT_MS } from "./support/timeouts";
import { chooseWorkers } from "./support/workers";

const ROUTE_GUARD = /route-coverage\.spec\.ts/;

const workerChoice = chooseWorkers();
const runId = process.env.E2E_RUN_ID;

if (!process.env.TEST_WORKER_INDEX) {
  console.log(
    `e2e: ${workerChoice.workers} workers (${workerChoice.source})${runId ? `, run ${runId}` : ""}`,
  );
}

export default defineConfig({
  testDir: "./specs",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: workerChoice.workers,
  outputDir: runId ? `test-results/${runId}` : "test-results",
  reporter: [
    ["list"],
    [
      "html",
      { open: "never", outputFolder: runId ? `playwright-report/${runId}` : "playwright-report" },
    ],
  ],
  timeout: TEST_TIMEOUT_MS,
  expect: { timeout: EXPECT_TIMEOUT_MS },
  use: {
    baseURL: env.frontendBaseUrl,
    extraHTTPHeaders: browserOriginHeaders,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "guard",
      testMatch: ROUTE_GUARD,
    },
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "desktop-chromium",
      testIgnore: ROUTE_GUARD,
      grepInvert: /@phone-only/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "phone-chromium",
      testIgnore: ROUTE_GUARD,
      grep: /@phone(-only)?\b/,
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
