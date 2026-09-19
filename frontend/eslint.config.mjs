import { createRequire } from "node:module";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import boundaries from "eslint-plugin-boundaries";
import jsdoc from "eslint-plugin-jsdoc";
import useClient from "eslint-plugin-use-client";

const require = createRequire(import.meta.url);
const noCommentsExceptTsdoc = require("./tools/eslint/no-comments-except-tsdoc.cjs");

export default defineConfig([
  globalIgnores([".next/**", "coverage/**", "node_modules/**", "src/lib/api/generated/**"]),
  ...nextVitals,
  {
    files: ["src/**/*.{ts,tsx}", "tools/**/*.{js,cjs}"],
    plugins: { local: { rules: { "no-comments-except-tsdoc": noCommentsExceptTsdoc } } },
    rules: { "local/no-comments-except-tsdoc": "error" },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { jsdoc },
    rules: {
      "jsdoc/require-description": "error",
      "jsdoc/no-types": "error",
      "jsdoc/check-alignment": "error",
      "jsdoc/check-tag-names": ["error", { typed: true }],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}", "src/**/*.node.test.ts", "src/testing/**"],
    plugins: { "use-client": useClient },
    rules: {
      "use-client/require-use-client": ["error", { removeUnnecessary: true }],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { boundaries },
    settings: {
      "boundaries/include": ["src/**/*"],
      "boundaries/dependency-nodes": ["import", "dynamic-import", "require"],
      "import/resolver": {
        typescript: { alwaysTryTypes: true, project: "./tsconfig.json" },
        node: true,
      },
      "boundaries/elements": [
        { type: "app", pattern: "src/app" },
        { type: "feature", pattern: "src/features/*", capture: ["featureName"] },
        { type: "ui", pattern: "src/components" },
        { type: "lib", pattern: "src/lib" },
        { type: "testing", pattern: "src/testing" },
      ],
    },
    rules: {
      "boundaries/no-unknown-dependencies": "error",
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          policies: [
            {
              from: [{ element: { type: "app" } }],
              allow: [{ to: { element: { type: ["feature", "ui", "lib"] } } }],
            },
            {
              from: [{ element: { type: "feature" } }],
              allow: [
                { to: { element: { type: ["ui", "lib", "testing"] } } },
                {
                  to: {
                    element: {
                      type: "feature",
                      captured: { featureName: "{{from.captured.featureName}}" },
                    },
                  },
                },
              ],
            },
            {
              from: [{ element: { type: "ui" } }],
              allow: [{ to: { element: { type: ["ui", "lib"] } } }],
            },
            {
              from: [{ element: { type: "lib" } }],
              allow: [{ to: { element: { type: "lib" } } }],
            },
            {
              from: [{ element: { type: "testing" } }],
              allow: [{ to: { element: { type: ["app", "feature", "ui", "lib", "testing"] } } }],
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/server/*", "**/dal", "**/server-client"],
              message:
                "Server-only modules may not be imported here. Fetch in an RSC and pass props.",
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/app/**/*.{ts,tsx}",
      "src/features/*/server/**/*.{ts,tsx}",
      "src/features/*/actions/**/*.{ts,tsx}",
      "src/lib/auth/**/*.{ts,tsx}",
    ],
    rules: {
      "no-restricted-imports": "off",
    },
  },
]);
