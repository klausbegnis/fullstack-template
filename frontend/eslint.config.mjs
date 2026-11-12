import { createRequire } from "node:module";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import boundaries from "eslint-plugin-boundaries";
import jsdoc from "eslint-plugin-jsdoc";
import testingLibrary from "eslint-plugin-testing-library";
import useClient from "eslint-plugin-use-client";
import vitest from "@vitest/eslint-plugin";

const require = createRequire(import.meta.url);
const noCommentsExceptTsdoc = require("./tools/eslint/no-comments-except-tsdoc.cjs");
const noImperativeEventHandlers = require("./tools/eslint/no-imperative-event-handlers.cjs");

const featureLayers = [
  "feature-model",
  "feature-api",
  "feature-hooks",
  "feature-containers",
  "feature-components",
  "feature-server",
  "feature-actions",
  "feature-testing",
  "feature",
];

const sameFeature = (types) => ({
  to: {
    element: {
      type: types,
      captured: { featureName: "{{from.captured.featureName}}" },
    },
  },
});

const sharedFromFeature = { to: { element: { type: ["ui", "lib", "testing"] } } };

const featurePolicy = (from, allowedLayers) => ({
  from: [{ element: { type: from } }],
  allow: [sharedFromFeature, sameFeature([from, ...allowedLayers])],
});

const clientDirectoryGlobs = [
  "src/features/*/components/**/*.{ts,tsx}",
  "src/features/*/model/**/*.{ts,tsx}",
  "src/features/*/api/**/*.{ts,tsx}",
  "src/features/*/server/**/*.{ts,tsx}",
  "src/features/*/hooks/**/*.{ts,tsx}",
  "src/features/*/testing/**/*.{ts,tsx}",
];

const testGlobs = ["src/**/*.test.{ts,tsx}", "src/**/*.node.test.ts", "src/testing/**/*.{ts,tsx}"];

const noProcessEnv = {
  selector: "MemberExpression[object.name='process'][property.name='env']",
  message: "Read environment variables only in src/lib/env.ts, which validates them with zod.",
};

const noUseClientDirective = {
  selector: "Program > ExpressionStatement > Literal[value='use client']",
  message:
    "'use client' belongs in containers/ (or components/, app/, lib/query/). This layer must stay server-renderable.",
};

const testRestrictions = [
  {
    selector:
      "CallExpression[callee.object.name='vi'][callee.property.name='mock'] > Literal[value=/lib\\/api\\/generated/]",
    message: "Never mock the generated API client. Intercept the network with MSW instead.",
  },
  {
    selector:
      "CallExpression[callee.name=/^(get|getAll|query|queryAll|find|findAll)ByTestId$/], CallExpression[callee.property.name=/^(get|getAll|query|queryAll|find|findAll)ByTestId$/]",
    message: "Query by role, label or text. Test ids couple the test to the markup.",
  },
  {
    selector: "MemberExpression[property.name=/^toMatch(Inline)?Snapshot$/]",
    message: "Snapshots assert nothing. Assert the behaviour the user observes.",
  },
];

export default defineConfig([
  globalIgnores([".next/**", "coverage/**", "node_modules/**", "src/lib/api/generated/**"]),
  ...nextVitals,
  {
    files: ["src/**/*.{ts,tsx}", "tools/**/*.{js,cjs}"],
    plugins: {
      local: {
        rules: {
          "no-comments-except-tsdoc": noCommentsExceptTsdoc,
          "no-imperative-event-handlers": noImperativeEventHandlers,
        },
      },
    },
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
    ignores: [
      "src/**/*.test.{ts,tsx}",
      "src/**/*.node.test.ts",
      "src/testing/**",
      "src/features/*/api/**",
      "src/features/*/hooks/**",
    ],
    plugins: { "use-client": useClient },
    rules: {
      "use-client/require-use-client": ["error", { removeUnnecessary: true }],
    },
  },
  {
    files: ["src/features/*/components/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}", "src/**/*.node.test.ts"],
    plugins: { "use-client": useClient },
    rules: {
      "use-client/require-use-client": ["error", { eventHandlers: false, removeUnnecessary: true }],
      "local/no-imperative-event-handlers": "error",
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
        { type: "feature-model", pattern: "src/features/*/model", capture: ["featureName"] },
        { type: "feature-api", pattern: "src/features/*/api", capture: ["featureName"] },
        { type: "feature-hooks", pattern: "src/features/*/hooks", capture: ["featureName"] },
        {
          type: "feature-containers",
          pattern: "src/features/*/containers",
          capture: ["featureName"],
        },
        {
          type: "feature-components",
          pattern: "src/features/*/components",
          capture: ["featureName"],
        },
        { type: "feature-server", pattern: "src/features/*/server", capture: ["featureName"] },
        { type: "feature-actions", pattern: "src/features/*/actions", capture: ["featureName"] },
        { type: "feature-testing", pattern: "src/features/*/testing", capture: ["featureName"] },
        { type: "feature", pattern: "src/features/*", capture: ["featureName"] },
        { type: "ui", pattern: "src/components" },
        { type: "lib", pattern: "src/lib" },
        { type: "testing", pattern: "src/testing" },
      ],
    },
    rules: {
      "boundaries/no-unknown-dependencies": "error",
      "boundaries/external": [
        "error",
        {
          default: "allow",
          policies: [
            {
              from: [{ element: { type: "feature-model" } }],
              disallow: ["react", "react-dom", "next", "next/*", "@tanstack/*"],
              message:
                "model/ holds plain types, zod schemas and pure functions. Framework code belongs in the layers above it.",
            },
            {
              from: [{ element: { type: "feature-components" } }],
              disallow: ["@tanstack/*", "next/navigation"],
              message:
                "components/ are props-only views that render on the server. Data and navigation belong to containers/.",
            },
          ],
        },
      ],
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          policies: [
            {
              from: [{ element: { type: "app" } }],
              allow: [
                {
                  to: {
                    element: {
                      type: [
                        "feature-containers",
                        "feature-server",
                        "feature-api",
                        "feature-model",
                        "ui",
                        "lib",
                      ],
                    },
                  },
                },
              ],
            },
            featurePolicy("feature-model", []),
            featurePolicy("feature-containers", [
              "feature-hooks",
              "feature-api",
              "feature-model",
              "feature-components",
              "feature-actions",
              "feature-testing",
            ]),
            featurePolicy("feature-hooks", ["feature-api", "feature-model", "feature-testing"]),
            featurePolicy("feature-api", ["feature-model", "feature-testing"]),
            featurePolicy("feature-components", ["feature-model", "feature-testing"]),
            featurePolicy("feature-server", ["feature-api", "feature-model", "feature-testing"]),
            featurePolicy("feature-actions", ["feature-model", "feature-testing"]),
            featurePolicy("feature-testing", ["feature-model", "feature-api"]),
            featurePolicy("feature", featureLayers),
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
              allow: [
                { to: { element: { type: ["app", "ui", "lib", "testing", ...featureLayers] } } },
              ],
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "react/no-unstable-nested-components": "error",
      "react/jsx-no-leaked-render": "error",
      "react/forbid-dom-props": ["error", { forbid: ["style"] }],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}", "tools/**/*.{js,cjs}"],
    ignores: ["src/lib/env.ts"],
    rules: { "no-restricted-syntax": ["error", noProcessEnv] },
  },
  {
    files: clientDirectoryGlobs,
    rules: { "no-restricted-syntax": ["error", noProcessEnv, noUseClientDirective] },
  },
  {
    files: testGlobs,
    plugins: { "testing-library": testingLibrary, vitest },
    rules: {
      "no-restricted-syntax": ["error", noProcessEnv, noUseClientDirective, ...testRestrictions],
      "testing-library/prefer-screen-queries": "error",
      "testing-library/no-node-access": "error",
      "testing-library/no-container": "error",
      "testing-library/prefer-user-event": "error",
      "testing-library/no-debugging-utils": "error",
      "testing-library/render-result-naming-convention": "error",
      "vitest/no-focused-tests": "error",
      "vitest/no-disabled-tests": "error",
      "vitest/expect-expect": "error",
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/components/ui/**"],
    rules: {
      "no-restricted-properties": [
        "error",
        {
          property: "showModal",
          message:
            "Open modals through useModalDialog from components/ui (outside click + Escape + focus return).",
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
