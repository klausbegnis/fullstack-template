import { expect, test } from "../fixtures/test";
import { loginThroughForm, logout } from "../flows/auth";
import { LOGIN_HEADING, USERS_HEADING } from "../routes/route-manifest";

test.describe("authentication", () => {
  test("an admin signing in through the form lands on the users list", async ({ page, seed }) => {
    const admin = seed.users.admin;
    await loginThroughForm(page, admin.email, admin.password);
    await expect(page).toHaveURL(/\/users$/);
    await expect(page.getByRole("heading", { level: 1, name: USERS_HEADING })).toBeVisible();
    await expect(page.getByRole("button", { name: `Account of ${admin.name}` })).toBeVisible();
  });

  test("a wrong password shows an error and stays on login", async ({ page, seed }) => {
    await loginThroughForm(page, seed.users.member.email, "not-the-password");
    await expect(
      page.getByRole("alert").filter({ hasText: "Authentication required" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { level: 1, name: LOGIN_HEADING })).toBeVisible();
  });

  test("signing out through the account menu closes protected pages", async ({ page, seed }) => {
    const admin = seed.users.admin;
    await loginThroughForm(page, admin.email, admin.password);
    await expect(page).toHaveURL(/\/users$/);

    await logout(page, admin.name);

    await expect(page).toHaveURL(/\/login$/);
    await page.goto(`/users/${seed.users.member.id}`);
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("signing in with a next path returns to it", async ({ page, seed }) => {
    const member = seed.users.member;
    const ownPage = `/users/${member.id}`;
    await page.goto(`/login?next=${encodeURIComponent(ownPage)}`);

    await loginThroughForm(page, member.email, member.password);

    await expect(page).toHaveURL(ownPage);
    await expect(page.getByRole("heading", { level: 1, name: member.name })).toBeVisible();
  });
});
