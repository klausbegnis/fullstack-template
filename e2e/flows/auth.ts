import { expect, type Page } from "@playwright/test";

/** Fills the login form with its labelled fields and submits it. */
export async function loginThroughForm(page: Page, email: string, password: string): Promise<void> {
  if (!new URL(page.url(), "http://unset.invalid").pathname.startsWith("/login")) {
    await page.goto("/login");
  }
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Opens the header's account menu of the signed-in user named `name`. */
export async function openAccountMenu(page: Page, name: string): Promise<void> {
  await page.getByRole("button", { name: `Account of ${name}` }).click();
  await expect(page.getByRole("menu", { name: `Account of ${name}` })).toBeVisible();
}

/** Signs out through the account menu's logout item. */
export async function logout(page: Page, name: string): Promise<void> {
  await openAccountMenu(page, name);
  await page.getByRole("menuitem", { name: "Log out" }).click();
}
