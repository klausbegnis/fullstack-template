import { expect, type Locator, type Page } from "@playwright/test";

const USERS_PAGER = "Users pagination";

/**
 * Opens the users list and pages forward until the link of the user named `name` shows, failing
 * when the last page is reached without it. Each step waits for the rows to change, because the
 * list keeps the previous page on screen while the next one loads.
 */
export async function findUserInList(page: Page, name: string): Promise<Locator> {
  await page.goto("/users");
  await expect(page.getByRole("table")).toBeVisible();
  const link = page.getByRole("link", { name, exact: true });
  const next = page.getByRole("navigation", { name: USERS_PAGER }).getByRole("button", {
    name: "Next",
  });
  const firstRowLink = page.getByRole("row").nth(1).getByRole("link");
  while (!(await link.isVisible())) {
    await expect(next, `${name} is on no page of the users list`).toBeEnabled();
    const before = await firstRowLink.textContent();
    await next.click();
    await expect(firstRowLink).not.toHaveText(before ?? "");
  }
  return link;
}

/** The modal that confirms disabling a user. */
export function disableDialog(page: Page): Locator {
  return page.getByRole("dialog", { name: "Disable this user?" });
}

/** Opens the disable confirmation from a user's detail page. */
export async function openDisableDialog(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: "Disable user" }).click();
  const dialog = disableDialog(page);
  await expect(dialog).toBeVisible();
  return dialog;
}
