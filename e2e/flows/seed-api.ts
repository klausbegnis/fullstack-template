import { randomUUID } from "node:crypto";
import { request, type APIRequestContext, type APIResponse } from "@playwright/test";
import { browserOriginHeaders, env } from "../support/env";
import { SEEDED_PASSWORD, type Role } from "../support/personas";

export interface SeededUser {
  id: string;
  name: string;
  email: string;
  password: string;
}

export interface Seed {
  runId: string;
  users: Record<Role, SeededUser>;
}

interface UserDto {
  id: string;
  name: string;
  email: string;
}

const CSRF_COOKIE = "app_csrf";

const BOOTSTRAP_HINT =
  "Bootstrap the admin first: docker compose exec -T api python -m app.commands.bootstrap_admin " +
  `${env.adminEmail} --password <password> --yes (then export E2E_ADMIN_PASSWORD if it is not the default).`;

async function readJson<T>(response: APIResponse, action: string): Promise<T> {
  if (!response.ok()) {
    throw new Error(`${action} failed with ${response.status()}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

async function readData<T>(response: APIResponse, action: string): Promise<T> {
  const envelope = await readJson<{ data: T }>(response, action);
  return envelope.data;
}

/** A short id that keeps the emails and names one run creates apart from every other run's. */
export function newRunId(): string {
  return `${Date.now().toString(36)}-${randomUUID().slice(0, 6)}`;
}

/**
 * Opens an API session for one user through the frontend's `/api` proxy, as the browser signs in.
 * The caller disposes of it.
 */
export async function signIn(email: string, password: string): Promise<APIRequestContext> {
  const context = await request.newContext({
    baseURL: env.frontendBaseUrl,
    extraHTTPHeaders: browserOriginHeaders,
  });
  const response = await context.post("/api/auth/login", { data: { email, password } });
  if (response.status() === 401) {
    await context.dispose();
    throw new Error(`Seeding could not sign in as ${email}. ${BOOTSTRAP_HINT}`);
  }
  await readJson<UserDto>(response, `Sign in as ${email}`);
  return context;
}

/**
 * The headers a browser mutation carries: the allowed `Origin` the API demands of a
 * cookie-authenticated mutation, and the double-submit `X-CSRF-Token` copied from `app_csrf`.
 */
export async function mutationHeaders(context: APIRequestContext): Promise<Record<string, string>> {
  const { cookies } = await context.storageState();
  const csrf = cookies.find((cookie) => cookie.name === CSRF_COOKIE)?.value;
  if (csrf === undefined) {
    throw new Error("The session carries no app_csrf cookie; sign in before mutating.");
  }
  return { ...browserOriginHeaders, "X-CSRF-Token": csrf };
}

/** The user a signed-in API session belongs to. */
export async function currentUser(context: APIRequestContext): Promise<UserDto> {
  return readJson<UserDto>(await context.get("/api/auth/me"), "Read the signed-in user");
}

/** What a spec chooses about a user it creates; the rest comes from `createUser`. */
export interface NewUser {
  label: string;
  runId: string;
  role?: Role;
}

/** Creates a run-unique user with `SEEDED_PASSWORD` from an admin's API session. */
export async function createUser(
  admin: APIRequestContext,
  { label, runId, role = "member" }: NewUser,
): Promise<SeededUser> {
  const name = `E2E ${label} ${runId}`;
  const email = `e2e-${label}-${runId}@example.test`;
  const created = await readData<UserDto>(
    await admin.post("/api/users", {
      headers: await mutationHeaders(admin),
      data: { name, email, password: SEEDED_PASSWORD, role },
    }),
    `Create the ${role} ${email}`,
  );
  return { id: created.id, name, email, password: SEEDED_PASSWORD };
}

/** Signs in as the bootstrapped admin and creates this run's member. */
export async function seedThroughApi(): Promise<Seed> {
  const runId = newRunId();
  const admin = await signIn(env.adminEmail, env.adminPassword);
  try {
    const adminUser = await currentUser(admin);
    const member = await createUser(admin, { label: "member", runId });
    return {
      runId,
      users: {
        admin: {
          id: adminUser.id,
          name: adminUser.name,
          email: env.adminEmail,
          password: env.adminPassword,
        },
        member,
      },
    };
  } finally {
    await admin.dispose();
  }
}
