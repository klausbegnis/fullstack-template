import { expect, type Page } from "@playwright/test";
import { urlMatchesPattern } from "../routes/route-patterns";
import { CONSOLE_ALLOWANCES } from "../support/known-findings";

export type GuardIssueKind = "console-error" | "page-error" | "server-error";

export interface GuardIssue {
  kind: GuardIssueKind;
  pageUrl: string;
  detail: string;
}

interface Allowance {
  kind: GuardIssueKind;
  pattern: RegExp;
  reason: string;
}

/** Collects console errors, uncaught page errors and 5xx responses from every watched page. */
export class PageGuards {
  private readonly issues: GuardIssue[] = [];
  private readonly allowances: Allowance[] = [];

  watch(page: Page): void {
    page.on("console", (message) => {
      if (message.type() === "error") {
        this.issues.push({ kind: "console-error", pageUrl: page.url(), detail: message.text() });
      }
    });
    page.on("pageerror", (error) => {
      this.issues.push({ kind: "page-error", pageUrl: page.url(), detail: error.message });
    });
    page.on("response", (response) => {
      if (response.status() >= 500) {
        this.issues.push({
          kind: "server-error",
          pageUrl: page.url(),
          detail: `${response.status()} ${response.request().method()} ${response.url()}`,
        });
      }
    });
  }

  /** Tolerates one expected error in this test only; the reason is attached to the report. */
  allow(kind: GuardIssueKind, pattern: RegExp, reason: string): void {
    this.allowances.push({ kind, pattern, reason });
  }

  unexpected(): GuardIssue[] {
    return this.issues.filter((issue) => !this.isAllowed(issue));
  }

  expectClean(): void {
    expect(this.unexpected(), "console errors, page errors or 5xx responses").toEqual([]);
  }

  private isAllowed(issue: GuardIssue): boolean {
    const perTest = this.allowances.some(
      (allowance) => allowance.kind === issue.kind && allowance.pattern.test(issue.detail),
    );
    const reviewed =
      issue.kind === "console-error" &&
      CONSOLE_ALLOWANCES.some(
        (allowance) =>
          allowance.message.test(issue.detail) && safeMatch(issue.pageUrl, allowance.pattern),
      );
    return perTest || reviewed;
  }
}

function safeMatch(url: string, pattern: string): boolean {
  return URL.canParse(url) && urlMatchesPattern(url, pattern);
}
