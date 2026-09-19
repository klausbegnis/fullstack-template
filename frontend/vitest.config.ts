import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    projects: [
      {
        plugins: [tsconfigPaths(), react()],
        test: {
          name: "unit",
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: ["src/**/*.node.test.ts"],
          environment: "jsdom",
          setupFiles: ["./vitest.setup.ts"],
        },
      },
      {
        plugins: [tsconfigPaths()],
        test: {
          name: "node",
          include: ["src/**/*.node.test.ts"],
          environment: "node",
        },
      },
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
    },
  },
});
