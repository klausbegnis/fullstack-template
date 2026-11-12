import { readdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { navItems } from "../../frontend/src/components/layout/nav-items";
import { ROUTE_ALLOWLIST, ROUTE_MANIFEST } from "../routes/route-manifest";
import { pagePathToPattern } from "../routes/route-patterns";
import { HEADINGLESS_ROUTES } from "../support/known-findings";

const APP_DIR = path.resolve(import.meta.dirname, "..", "..", "frontend", "src", "app");

function appPagePatterns(): string[] {
  return readdirSync(APP_DIR, { recursive: true, encoding: "utf8" })
    .filter((entry) => path.basename(entry) === "page.tsx")
    .map(pagePathToPattern)
    .sort();
}

const manifestPatterns = new Set(ROUTE_MANIFEST.map((entry) => entry.pattern));
const manifestTemplates = new Set(ROUTE_MANIFEST.map((entry) => entry.template));
const allowlistedPatterns = new Set(ROUTE_ALLOWLIST.map((entry) => entry.pattern));

test("the app tree has pages to guard", () => {
  expect(appPagePatterns().length).toBeGreaterThan(0);
});

test("every page.tsx route is smoke-tested or allowlisted with a reason", () => {
  const uncovered = appPagePatterns().filter(
    (pattern) => !manifestPatterns.has(pattern) && !allowlistedPatterns.has(pattern),
  );
  expect(uncovered, "routes with no smoke coverage and no allowlist entry").toEqual([]);
});

test("every navigation link is a smoke target", () => {
  const missing = navItems.map((item) => item.href).filter((href) => !manifestTemplates.has(href));
  expect(missing, "navigation links missing from the route manifest").toEqual([]);
});

test("every redirect target is itself a smoke target", () => {
  const targets = ROUTE_MANIFEST.flatMap((entry) =>
    entry.redirectsTo === undefined ? [] : [entry.redirectsTo.split("?")[0] ?? ""],
  );
  expect(targets.filter((target) => !manifestTemplates.has(target))).toEqual([]);
});

test("every admin route says what a member gets there", () => {
  const unstated = ROUTE_MANIFEST.filter(
    (entry) => entry.audience === "admin" && entry.memberOutcome === undefined,
  ).map((entry) => entry.pattern);
  expect(unstated, "admin routes without a memberOutcome").toEqual([]);
});

test("the allowlist names only real routes that the smoke run does not cover", () => {
  const pages = new Set(appPagePatterns());
  const stale = ROUTE_ALLOWLIST.filter(
    (entry) => !pages.has(entry.pattern) || manifestPatterns.has(entry.pattern),
  );
  expect(stale, "stale allowlist entries").toEqual([]);
  expect(ROUTE_ALLOWLIST.filter((entry) => entry.reason.trim() === "")).toEqual([]);
});

test("the manifest names only real routes", () => {
  const pages = new Set(appPagePatterns());
  expect(ROUTE_MANIFEST.filter((entry) => !pages.has(entry.pattern))).toEqual([]);
});

test("every headingless smoke target has a reviewed finding", () => {
  const reviewed = new Set(HEADINGLESS_ROUTES.map((finding) => finding.pattern));
  const headingless = ROUTE_MANIFEST.filter((entry) => entry.heading === null).map(
    (entry) => entry.pattern,
  );
  expect(headingless.filter((pattern) => !reviewed.has(pattern))).toEqual([]);
  expect([...reviewed].filter((pattern) => !headingless.includes(pattern))).toEqual([]);
});
