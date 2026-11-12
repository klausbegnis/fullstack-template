function read(name: string, fallback: string): string {
  const value = process.env[name];
  return value === undefined || value === "" ? fallback : value;
}

export const env = {
  frontendBaseUrl: read("FRONTEND_BASE_URL", "http://127.0.0.1:3000"),
  apiBaseUrl: read("API_BASE_URL", "http://127.0.0.1:8000"),
  adminEmail: read("E2E_ADMIN_EMAIL", "e2e-admin@example.test"),
  adminPassword: read("E2E_ADMIN_PASSWORD", "e2e-not-a-real-pw"),
} as const;

/**
 * The `Origin` a browser sends on every mutation. API request contexts send it too, because the API
 * refuses a cookie-authenticated mutation that proves no allowed origin.
 */
export const browserOriginHeaders = { Origin: new URL(env.frontendBaseUrl).origin } as const;
