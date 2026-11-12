import type { Browser, BrowserContext, Page, Response } from "@playwright/test";
import { expect, test } from "../fixtures/test";
import type { PageGuards } from "../fixtures/page-guards";
import type { Seed } from "../flows/seed-api";
import { browserOriginHeaders } from "../support/env";

const SESSION_COOKIES = ["app_access", "app_refresh", "app_csrf"] as const;
const EXPIRED_NOTICE = "Your session expired. Sign in again.";

interface SignedIn {
  context: BrowserContext;
  page: Page;
}

async function signInMemberOnItsOwnContext(
  browser: Browser,
  baseURL: string | undefined,
  seed: Seed,
  pageGuards: PageGuards,
): Promise<SignedIn> {
  const context = await browser.newContext({ baseURL, extraHTTPHeaders: browserOriginHeaders });
  const login = await context.request.post("/api/auth/login", {
    data: { email: seed.users.member.email, password: seed.users.member.password },
  });
  expect(login.status(), "sign the member in through the frontend proxy").toBe(200);
  const page = await context.newPage();
  pageGuards.watch(page);
  return { context, page };
}

function recordResponses(page: Page, path: string): Response[] {
  const seen: Response[] = [];
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === path) seen.push(response);
  });
  return seen;
}

function recordLoginVisits(page: Page): string[] {
  const visits: string[] = [];
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame() && new URL(frame.url()).pathname === "/login") {
      visits.push(frame.url());
    }
  });
  return visits;
}

async function cookieValue(context: BrowserContext, name: string): Promise<string> {
  return (await context.cookies()).find((cookie) => cookie.name === name)?.value ?? "";
}

async function sessionCookieNames(context: BrowserContext): Promise<string[]> {
  const names = (await context.cookies()).map((cookie) => cookie.name);
  return SESSION_COOKIES.filter((name) => names.includes(name));
}

test.describe("session renewal", () => {
  test("a missing access cookie renews on navigation and keeps the URL", async ({
    browser,
    baseURL,
    seed,
    pageGuards,
  }) => {
    const member = await signInMemberOnItsOwnContext(browser, baseURL, seed, pageGuards);
    const ownPage = `/users/${seed.users.member.id}`;
    try {
      const renewals = recordResponses(member.page, "/api/auth/renew");
      const loginVisits = recordLoginVisits(member.page);
      await member.context.clearCookies({ name: "app_access" });

      await member.page.goto(ownPage);

      await expect(member.page).toHaveURL(ownPage);
      await expect(
        member.page.getByRole("heading", { level: 1, name: seed.users.member.name }),
      ).toBeVisible();
      expect(renewals.map((response) => response.status())).toEqual([303]);
      expect(loginVisits).toEqual([]);
      expect(await sessionCookieNames(member.context)).toEqual([...SESSION_COOKIES]);
    } finally {
      await member.context.close();
    }
  });

  test("a session revoked elsewhere ends on login with the expired notice", async ({
    browser,
    baseURL,
    request,
    seed,
    pageGuards,
  }) => {
    const member = await signInMemberOnItsOwnContext(browser, baseURL, seed, pageGuards);
    try {
      const access = await cookieValue(member.context, "app_access");
      const csrf = await cookieValue(member.context, "app_csrf");
      const revoked = await request.post("/api/auth/logout", {
        headers: {
          ...browserOriginHeaders,
          Cookie: `app_access=${access}; app_csrf=${csrf}`,
          "X-CSRF-Token": csrf,
        },
      });
      expect(revoked.status(), "revoke the session from another client").toBe(204);
      await member.context.clearCookies({ name: "app_access" });
      const renewals = recordResponses(member.page, "/api/auth/renew");

      await member.page.goto(`/users/${seed.users.member.id}`);

      await expect(member.page).toHaveURL(/\/login\?next=.*&reason=expired$/);
      await expect(member.page.getByRole("status")).toHaveText(EXPIRED_NOTICE);
      await expect(member.page.getByRole("button", { name: "Sign in" })).toBeVisible();
      expect(renewals).toHaveLength(1);
      expect(await sessionCookieNames(member.context)).toEqual([]);
    } finally {
      await member.context.close();
    }
  });

  test("the login page announces an expired session", async ({ page }) => {
    await page.goto("/login?reason=expired");
    await expect(page.getByRole("status")).toHaveText(EXPIRED_NOTICE);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });
});
