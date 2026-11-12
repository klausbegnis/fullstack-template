import { readFileSync } from "node:fs";
import { test as base, type BrowserContext, type Page } from "@playwright/test";
import type { Seed } from "../flows/seed-api";
import { browserOriginHeaders } from "../support/env";
import { SEED_FILE, storageStatePath, type Role } from "../support/personas";
import { AxeChecker } from "./axe";
import { PageGuards } from "./page-guards";
import { RequestRecorder } from "./requests";

/** A page signed in as one seeded role, in a context of its own. */
export interface RoleSession {
  context: BrowserContext;
  page: Page;
}

/** Opens a fresh context with the stored session of `role`; the fixture closes it. */
export type AsRole = (role: Role) => Promise<RoleSession>;

interface TestFixtures {
  pageGuards: PageGuards;
  requests: RequestRecorder;
  axe: AxeChecker;
  asRole: AsRole;
}

interface WorkerFixtures {
  seed: Seed;
}

/** The suite's `test`: seeded data, role sessions, request recording, axe and page guards. */
export const test = base.extend<TestFixtures, WorkerFixtures>({
  seed: [
    async ({}, use) => {
      await use(JSON.parse(readFileSync(SEED_FILE, "utf8")) as Seed);
    },
    { scope: "worker" },
  ],
  pageGuards: [
    async ({}, use) => {
      const guards = new PageGuards();
      await use(guards);
      guards.expectClean();
    },
    { auto: true },
  ],
  requests: async ({}, use) => {
    await use(new RequestRecorder());
  },
  axe: async ({}, use, testInfo) => {
    await use(new AxeChecker(testInfo));
  },
  context: async ({ context, requests }, use) => {
    requests.watch(context);
    await use(context);
  },
  page: async ({ page, pageGuards }, use) => {
    pageGuards.watch(page);
    await use(page);
  },
  asRole: async (
    { browser, pageGuards, requests, baseURL, viewport, isMobile, hasTouch, userAgent },
    use,
  ) => {
    const contexts: BrowserContext[] = [];
    const open: AsRole = async (role) => {
      const context = await browser.newContext({
        baseURL,
        viewport,
        isMobile,
        hasTouch,
        userAgent,
        extraHTTPHeaders: browserOriginHeaders,
        storageState: storageStatePath(role),
      });
      contexts.push(context);
      requests.watch(context);
      const page = await context.newPage();
      pageGuards.watch(page);
      return { context, page };
    };
    await use(open);
    await Promise.all(contexts.map((context) => context.close()));
  },
});

export { expect } from "@playwright/test";
