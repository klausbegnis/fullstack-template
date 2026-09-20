import { readFileSync, readdirSync } from "node:fs";
import { basename, dirname, join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(import.meta.dirname, "..");

const GENERATED_PREFIX = "lib/api/generated/";

function walk(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolute = join(directory, entry.name);
    return entry.isDirectory() ? walk(absolute) : [absolute];
  });
}

function toSrcRelative(absolute: string): string {
  return relative(SRC_DIR, absolute).split(sep).join("/");
}

function read(srcRelativePath: string): string {
  return readFileSync(join(SRC_DIR, srcRelativePath), "utf8");
}

/**
 * Every file under `src/`, as a path relative to `src/` with POSIX
 * separators. Every rule below derives its subjects from this list, so
 * adding a feature never requires editing this test.
 */
export const SOURCE_FILES = walk(SRC_DIR).map(toSrcRelative);

const SOURCE_FILE_SET = new Set(SOURCE_FILES);

const isTestFile = (path: string) => /\.(test|node\.test)\.tsx?$/.test(path);

function layerFiles(layer: string, extension: string): string[] {
  const pattern = new RegExp(`^features/[^/]+/${layer}/[^/]+\\.${extension}$`);
  return SOURCE_FILES.filter((path) => pattern.test(path) && !isTestFile(path));
}

function missingSiblingTests(paths: string[], extension: string): string[] {
  return paths.filter(
    (path) =>
      !SOURCE_FILE_SET.has(path.replace(new RegExp(`\\.${extension}$`), `.test.${extension}`)),
  );
}

/**
 * True when a module's only exports are `type` or `interface` declarations.
 * Such a file has no behaviour to test, so the colocated-test rule skips it.
 */
export function exportsOnlyTypes(source: string): boolean {
  const exportStatements = source.match(/^export\s+.*/gm) ?? [];
  return (
    exportStatements.length > 0 &&
    exportStatements.every((statement) => /^export\s+(type|interface)\s/.test(statement))
  );
}

/**
 * An async `page.tsx` must own a `loading.tsx` and an `error.tsx` in its own
 * directory. Next.js would also accept a boundary inherited from an ancestor
 * segment, but every async page in this repo declares its own, and a
 * per-segment boundary is what makes a route's pending and failure states a
 * deliberate design decision rather than a fallback nobody chose.
 */
export const ROUTE_BOUNDARY_FILES = ["loading.tsx", "error.tsx"];

/**
 * Modules that run only on the server and must say so on their first line,
 * so importing one from a client component fails the build instead of
 * leaking cookies or the API base URL into the browser bundle.
 */
export const SERVER_ONLY_MODULES = [
  ...SOURCE_FILES.filter((path) => /^features\/[^/]+\/server\/[^/]+\.ts$/.test(path)),
  "lib/auth/dal.ts",
  "lib/api/server-client.ts",
];

describe("source layout", () => {
  it("has no barrel files outside the generated client", () => {
    const barrels = SOURCE_FILES.filter(
      (path) => /^index\.tsx?$/.test(basename(path)) && !path.startsWith(GENERATED_PREFIX),
    );

    expect(barrels).toEqual([]);
  });

  it("has no __tests__ directories", () => {
    const grouped = SOURCE_FILES.filter((path) => path.split("/").includes("__tests__"));

    expect(grouped).toEqual([]);
  });
});

describe("colocated tests", () => {
  it("covers every container", () => {
    expect(missingSiblingTests(layerFiles("containers", "tsx"), "tsx")).toEqual([]);
  });

  it("covers every component", () => {
    expect(missingSiblingTests(layerFiles("components", "tsx"), "tsx")).toEqual([]);
  });

  it("covers every hook", () => {
    expect(missingSiblingTests(layerFiles("hooks", "ts"), "ts")).toEqual([]);
  });

  it("covers every mapper", () => {
    const mappers = layerFiles("api", "ts").filter((path) => path.endsWith("-mapper.ts"));

    expect(missingSiblingTests(mappers, "ts")).toEqual([]);
  });

  it("covers every model module that is not type-only", () => {
    const withBehaviour = layerFiles("model", "ts").filter((path) => !exportsOnlyTypes(read(path)));

    expect(missingSiblingTests(withBehaviour, "ts")).toEqual([]);
  });
});

describe("route segments", () => {
  it("gives every async page its own loading and error boundary", () => {
    const asyncPages = SOURCE_FILES.filter(
      (path) =>
        /^app\/.*\/?page\.tsx$/.test(path) &&
        /export\s+default\s+async\s+function/.test(read(path)),
    );

    const missing = asyncPages.flatMap((page) =>
      ROUTE_BOUNDARY_FILES.filter(
        (boundary) => !SOURCE_FILE_SET.has(`${dirname(page)}/${boundary}`),
      ).map((boundary) => `${dirname(page)}/${boundary}`),
    );

    expect(missing).toEqual([]);
  });

  it("gates the authenticated route group on requireUser", () => {
    expect(read("app/(app)/layout.tsx")).toContain("requireUser(");
  });
});

describe("server-only modules", () => {
  it("declares server-only on the first line", () => {
    const missing = SERVER_ONLY_MODULES.filter(
      (path) => !read(path).trimStart().startsWith('import "server-only";'),
    );

    expect(missing).toEqual([]);
  });
});
