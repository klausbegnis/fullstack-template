import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";
import { urlMatchesPattern } from "../routes/route-patterns";
import { AXE_EXCLUSIONS } from "../support/known-findings";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const BLOCKING_IMPACTS = new Set(["serious", "critical"]);

/** Runs axe against a page and fails on serious or critical violations that are not reviewed exclusions. */
export class AxeChecker {
  constructor(private readonly testInfo: TestInfo) {}

  async expectNoBlockingViolations(page: Page): Promise<void> {
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    const blocking = results.violations.filter(
      (violation) =>
        BLOCKING_IMPACTS.has(violation.impact ?? "") &&
        !AXE_EXCLUSIONS.some(
          (exclusion) =>
            exclusion.ruleId === violation.id && urlMatchesPattern(page.url(), exclusion.pattern),
        ),
    );
    const summary = blocking.map((violation) => ({
      rule: violation.id,
      impact: violation.impact,
      help: violation.help,
      targets: violation.nodes.map((node) => node.target.join(" ")),
    }));
    if (summary.length > 0) {
      await this.testInfo.attach("axe-violations", {
        body: JSON.stringify(summary, null, 2),
        contentType: "application/json",
      });
    }
    expect(summary, `serious or critical axe violations on ${page.url()}`).toEqual([]);
  }
}
