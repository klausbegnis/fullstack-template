import { z } from "zod";

const serverEnvSchema = z.object({
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  API_PROXY_TARGET: z.url().default("http://localhost:8000"),
});

const publicEnvSchema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z.string().default("/api"),
});

/**
 * Server-only environment variables, parsed and validated once at import
 * time. Importing this module from client code is a build error because it
 * is only ever referenced from `server-only`-marked modules.
 */
export const serverEnv = serverEnvSchema.parse({
  NODE_ENV: process.env.NODE_ENV,
  API_PROXY_TARGET: process.env.API_PROXY_TARGET,
});

/**
 * Public environment variables inlined by Next.js at build time. Only
 * `NEXT_PUBLIC_*` variables belong here — never a secret.
 */
export const publicEnv = publicEnvSchema.parse({
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
});
