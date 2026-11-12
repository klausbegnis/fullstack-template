import { test } from "../fixtures/test";
import {
  allowAdminDataRefusal,
  expectMemberOutcome,
  expectRouteHealthy,
} from "../flows/route-smoke";
import { ROUTE_MANIFEST, type Audience, type RouteEntry } from "../routes/route-manifest";

const byAudience = (audience: Audience) =>
  ROUTE_MANIFEST.filter((entry) => entry.audience === audience);

const phoneTagUnlessRedirect = (entry: RouteEntry) =>
  entry.redirectsTo === undefined ? { tag: "@phone" } : {};

test.describe("public routes", () => {
  for (const entry of byAudience("public")) {
    test(
      `anonymous visitor sees ${entry.template}`,
      phoneTagUnlessRedirect(entry),
      async ({ page, seed, axe }) => {
        await expectRouteHealthy(page, entry, seed, "member", axe);
      },
    );
  }
});

test.describe("member routes", () => {
  for (const entry of byAudience("member")) {
    test(
      `member reaches ${entry.template}`,
      phoneTagUnlessRedirect(entry),
      async ({ asRole, seed, axe, pageGuards }) => {
        allowAdminDataRefusal(pageGuards);
        const { page } = await asRole("member");
        await expectRouteHealthy(page, entry, seed, "member", axe);
      },
    );
  }
  for (const entry of byAudience("admin")) {
    test(`member opening ${entry.template} gets what the app gives a member`, async ({
      asRole,
      seed,
      pageGuards,
    }) => {
      const { page } = await asRole("member");
      await expectMemberOutcome(page, entry, seed, pageGuards);
    });
  }
});

test.describe("admin routes", () => {
  for (const entry of [...byAudience("member"), ...byAudience("admin")]) {
    test(
      `admin sees ${entry.template}`,
      phoneTagUnlessRedirect(entry),
      async ({ asRole, seed, axe }) => {
        const { page } = await asRole("admin");
        await expectRouteHealthy(page, entry, seed, "admin", axe);
      },
    );
  }
});
