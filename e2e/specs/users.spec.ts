import { expect, test } from "../fixtures/test";
import { createUser, newRunId } from "../flows/seed-api";
import { disableDialog, findUserInList, openDisableDialog } from "../flows/users";
import { SEEDED_PASSWORD } from "../support/personas";

test.describe("user management", () => {
  test("admin creates a user through the form and finds it in the list", async ({ asRole }) => {
    const { page } = await asRole("admin");
    const runId = newRunId();
    const name = `E2E created ${runId}`;
    const email = `e2e-created-${runId}@example.test`;

    await page.goto("/users/new");
    await expect(page.getByRole("heading", { level: 1, name: "New user" })).toBeVisible();
    await page.getByLabel("Name").fill(name);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(SEEDED_PASSWORD);
    await page.getByLabel("Role").selectOption("member");
    await page.getByRole("button", { name: "Create user" }).click();

    await expect(page).toHaveURL(/\/users\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();

    const link = await findUserInList(page, name);
    const row = page.getByRole("row").filter({ has: link });
    await expect(row.getByRole("cell", { name: email })).toBeVisible();
    await expect(row.getByRole("cell", { name: "Active" })).toBeVisible();
  });

  test("admin renames a user and disables it after dismissing the confirmation twice", async ({
    asRole,
  }) => {
    const { context, page } = await asRole("admin");
    const runId = newRunId();
    const user = await createUser(context.request, { label: "edited", runId });
    const renamed = `E2E renamed ${runId}`;

    await page.goto(`/users/${user.id}`);
    await expect(page.getByRole("heading", { level: 1, name: user.name })).toBeVisible();
    await page.getByLabel("Name").fill(renamed);
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("heading", { level: 1, name: renamed })).toBeVisible();

    const escaped = await openDisableDialog(page);
    await page.keyboard.press("Escape");
    await expect(escaped).toBeHidden();

    const cancelled = await openDisableDialog(page);
    await cancelled.getByRole("button", { name: "Cancel" }).click();
    await expect(cancelled).toBeHidden();
    await expect(page.getByText("member · Active")).toBeVisible();

    const confirmed = await openDisableDialog(page);
    await confirmed.getByRole("button", { name: "Disable", exact: true }).click();
    await expect(disableDialog(page)).toBeHidden();
    await expect(page.getByText("member · Disabled")).toBeVisible();
    await expect(page.getByRole("button", { name: "Disable user" })).toBeHidden();

    const link = await findUserInList(page, renamed);
    await expect(
      page.getByRole("row").filter({ has: link }).getByRole("cell", { name: "Disabled" }),
    ).toBeVisible();
  });
});
