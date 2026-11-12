import { expect, test } from "../fixtures/test";
import { openAccountMenu } from "../flows/auth";
import { USERS_HEADING } from "../routes/route-manifest";

const PHONE_ONLY = { tag: "@phone-only" };

test.describe("phone shell", () => {
  test("the tab bar marks the current destination", PHONE_ONLY, async ({ asRole }) => {
    const { page } = await asRole("admin");
    await page.goto("/users");
    const tabs = page.getByRole("navigation", { name: "Tabs" });
    await expect(tabs.getByRole("link", { name: "Users" })).toHaveAttribute("aria-current", "page");
    await page.goto("/users/new");
    await expect(tabs.getByRole("link", { name: "Users" })).toHaveAttribute("aria-current", "page");
    await tabs.getByRole("link", { name: "Users" }).click();
    await expect(page).toHaveURL(/\/users$/);
    await expect(page.getByRole("heading", { level: 1, name: USERS_HEADING })).toBeVisible();
  });

  test(
    "the header menu opens the navigation and closes on Escape",
    PHONE_ONLY,
    async ({ asRole, axe }) => {
      const { page } = await asRole("admin");
      await page.goto("/users");
      const primary = page.getByRole("navigation", { name: "Primary" });
      await expect(primary).toBeHidden();

      await page.getByRole("button", { name: "Open menu" }).click();
      await expect(primary.getByRole("link", { name: "Users" })).toBeVisible();
      await axe.expectNoBlockingViolations(page);

      await page.keyboard.press("Escape");
      await expect(primary).toBeHidden();
      await expect(page.getByRole("button", { name: "Open menu" })).toBeFocused();
    },
  );

  test("the account menu opens from the header", PHONE_ONLY, async ({ asRole, seed }) => {
    const { page } = await asRole("member");
    await page.goto(`/users/${seed.users.member.id}`);
    await openAccountMenu(page, seed.users.member.name);
    await expect(page.getByRole("menuitem", { name: "Log out" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menuitem", { name: "Log out" })).toBeHidden();
  });
});
