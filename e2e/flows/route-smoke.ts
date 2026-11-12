import { expect, type Page } from "@playwright/test";
import type { AxeChecker } from "../fixtures/axe";
import type { PageGuards } from "../fixtures/page-guards";
import {
  OTHER_USER_ID,
  OTHER_USER_NAME,
  type MemberOutcome,
  type RouteEntry,
} from "../routes/route-manifest";
import { urlMatchesPattern } from "../routes/route-patterns";
import { HEADINGLESS_ROUTES, OVERFLOW_EXCLUSIONS } from "../support/known-findings";
import type { Role } from "../support/personas";
import type { Seed } from "./seed-api";

const OTHER_ROLE: Record<Role, Role> = { admin: "member", member: "admin" };

/** Replaces the manifest placeholders with a seeded user other than the viewer. */
export function resolveSeeded(text: string, seed: Seed, viewer: Role): string {
  const other = seed.users[OTHER_ROLE[viewer]];
  return text.replaceAll(OTHER_USER_ID, other.id).replaceAll(OTHER_USER_NAME, other.name);
}

function headingName(entry: RouteEntry, seed: Seed, viewer: Role): string | RegExp | null {
  return typeof entry.heading === "string"
    ? resolveSeeded(entry.heading, seed, viewer)
    : entry.heading;
}

async function expectMainAnchor(
  page: Page,
  entry: RouteEntry,
  seed: Seed,
  viewer: Role,
): Promise<void> {
  const name = headingName(entry, seed, viewer);
  if (name !== null) {
    await expect(page.getByRole("heading", { level: 1, name, exact: true })).toBeVisible();
    return;
  }
  const finding = HEADINGLESS_ROUTES.find((candidate) => candidate.pattern === entry.pattern);
  if (finding === undefined) {
    throw new Error(`${entry.pattern} has no heading and no reviewed headingless finding`);
  }
  await expect(page.getByRole(finding.anchor.role, { name: finding.anchor.name })).toBeVisible();
}

function isOverflowExcluded(url: string, viewportWidth: number): boolean {
  return OVERFLOW_EXCLUSIONS.some(
    (exclusion) =>
      viewportWidth <= exclusion.maxViewportWidth && urlMatchesPattern(url, exclusion.pattern),
  );
}

/** Asserts the page fits its viewport horizontally, unless a reviewed exclusion covers it. */
export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const size = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  if (isOverflowExcluded(page.url(), size.clientWidth)) {
    return;
  }
  expect(size.scrollWidth, `horizontal overflow on ${page.url()}`).toBeLessThanOrEqual(
    size.clientWidth,
  );
}

async function expectRedirectedTo(page: Page, expected: string): Promise<void> {
  await expect(page).toHaveURL((url) => `${url.pathname}${url.search}` === expected);
}

/**
 * Visits one manifest entry as `viewer` and asserts its status, heading, layout width and
 * accessibility. A redirect entry asserts where it lands instead; its target is a smoke target of
 * its own.
 */
export async function expectRouteHealthy(
  page: Page,
  entry: RouteEntry,
  seed: Seed,
  viewer: Role,
  axe: AxeChecker,
): Promise<void> {
  const response = await page.goto(resolveSeeded(entry.template, seed, viewer));
  expect(response?.status() ?? 0, `document status for ${entry.template}`).toBeLessThan(400);
  if (entry.redirectsTo !== undefined) {
    await expectRedirectedTo(page, resolveSeeded(entry.redirectsTo, seed, viewer));
    await expectMainAnchor(page, entry, seed, viewer);
    return;
  }
  await expectMainAnchor(page, entry, seed, viewer);
  await expectNoHorizontalOverflow(page);
  await axe.expectNoBlockingViolations(page);
}

/**
 * Tolerates the 403s the API answers when a member's page asks for admin-only data; the browser
 * logs each one, the first try and every query retry, as a console error.
 */
export function allowAdminDataRefusal(pageGuards: PageGuards): void {
  pageGuards.allow(
    "console-error",
    /status of 403/,
    "The API refuses admin-only data to a member with 403, and the browser logs each refusal.",
  );
}

/** The outcome a member gets on an admin entry, failing when the manifest names none. */
export function memberOutcomeOf(entry: RouteEntry): MemberOutcome {
  if (entry.memberOutcome === undefined) {
    throw new Error(`${entry.pattern} is an admin route with no memberOutcome in the manifest`);
  }
  return entry.memberOutcome;
}

/** Visits one admin entry as the member and asserts what the app gives them. */
export async function expectMemberOutcome(
  page: Page,
  entry: RouteEntry,
  seed: Seed,
  pageGuards: PageGuards,
): Promise<void> {
  const outcome = memberOutcomeOf(entry);
  allowAdminDataRefusal(pageGuards);
  const response = await page.goto(resolveSeeded(entry.template, seed, "member"));
  expect(response?.status() ?? 0, `document status for ${entry.template}`).toBeLessThan(400);
  await expect(page).toHaveURL((url) => urlMatchesPattern(url.toString(), entry.pattern));
  if (outcome.kind === "load-refused") {
    await expect(page.getByRole("alert").filter({ hasText: outcome.alert })).toBeVisible();
    return;
  }
  await expectMainAnchor(page, entry, seed, "member");
}
