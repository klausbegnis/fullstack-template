import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, request, test as setup } from "@playwright/test";
import { seedThroughApi } from "../flows/seed-api";
import { browserOriginHeaders, env } from "../support/env";
import { ROLES, SEED_FILE, storageStatePath } from "../support/personas";

setup("seed a run-unique member and store one session per role", async () => {
  const seed = await seedThroughApi();
  await mkdir(path.dirname(SEED_FILE), { recursive: true });
  await writeFile(SEED_FILE, JSON.stringify(seed, null, 2));

  for (const role of ROLES) {
    const user = seed.users[role];
    const context = await request.newContext({
      baseURL: env.frontendBaseUrl,
      extraHTTPHeaders: browserOriginHeaders,
    });
    const response = await context.post("/api/auth/login", {
      data: { email: user.email, password: user.password },
    });
    expect(response.status(), `login as ${role} through the frontend proxy`).toBe(200);
    await context.storageState({ path: storageStatePath(role) });
    await context.dispose();
  }
});
