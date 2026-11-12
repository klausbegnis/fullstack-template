import { createRequire } from "node:module";
import { defineConfig, globalIgnores } from "eslint/config";
import playwright from "eslint-plugin-playwright";
import tseslint from "typescript-eslint";

const require = createRequire(import.meta.url);
const noCommentsExceptTsdoc = require("../frontend/tools/eslint/no-comments-except-tsdoc.cjs");

export default defineConfig([
  globalIgnores(["node_modules/**", "playwright-report/**", "test-results/**", ".auth/**"]),
  {
    files: ["**/*.{ts,mts,mjs}"],
    languageOptions: {
      parser: tseslint.parser,
      ecmaVersion: "latest",
      sourceType: "module",
    },
    plugins: {
      local: { rules: { "no-comments-except-tsdoc": noCommentsExceptTsdoc } },
    },
    rules: {
      "local/no-comments-except-tsdoc": "error",
    },
  },
  {
    ...playwright.configs["flat/recommended"],
    files: ["**/*.ts"],
    rules: {
      ...playwright.configs["flat/recommended"].rules,
      "playwright/no-wait-for-timeout": "error",
      "playwright/no-wait-for-selector": "error",
      "playwright/no-networkidle": "error",
      "playwright/no-raw-locators": "error",
      "playwright/no-element-handle": "error",
      "playwright/no-eval": "error",
      "playwright/no-focused-test": "error",
      "playwright/no-skipped-test": "error",
      "playwright/no-page-pause": "error",
      "playwright/no-conditional-in-test": "error",
      "playwright/no-conditional-expect": "error",
      "playwright/prefer-web-first-assertions": "error",
      "playwright/missing-playwright-await": "error",
      "playwright/no-restricted-locators": [
        "error",
        [{ type: "getByTestId", message: "Locate by role, label or text, never by test id." }],
      ],
      "playwright/expect-expect": [
        "error",
        { assertFunctionPatterns: ["^expect[A-Z]", "\\.expect[A-Z]"] },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/^\\s*(xpath=|css=|\\/\\/|\\.\\/\\/)/]",
          message: "CSS and XPath selectors are banned; locate by role, label or text.",
        },
        {
          selector: "CallExpression[callee.property.name=/^\\$\\$?$/]",
          message: "page.$ and page.$$ return element handles; locate by role, label or text.",
        },
        {
          selector: "CallExpression[callee.property.name='waitForTimeout']",
          message: "Wait on a web-first assertion, never on time.",
        },
      ],
    },
  },
]);
