import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { API_PREFIX } from "./api/ApiClient";

const SRC = join(process.cwd(), "src");

// The only allowed REST resources (the API contract). Nothing else.
const ALLOWED_PATHS = new Set(["/searches", "/jobs", "/providers", "/knowledge", "/system"]);

function topLevel(path: string): string {
  const segment = path.split("/")[1];
  return segment === undefined ? "/" : `/${segment}`;
}

describe("API contract exclusivity", () => {
  it("ApiClient uses the /api/v1 prefix", () => {
    expect(API_PREFIX).toBe("/api/v1");
  });

  it("every endpoint referenced in the stores is an allowed /api/v1 resource", () => {
    for (const file of ["searches.ts", "jobs.ts", "providers.ts", "knowledge.ts", "system.ts"]) {
      const content = readFileSync(join(SRC, "state", file), "utf8");
      const matches = [...content.matchAll(/apiClient\.(get|post)<[^>]*>\(\"(\/[^\"]+)\"/g)]
        .map((m) => m[2])
        .filter((x): x is string => x !== undefined);
      expect(matches.length).toBeGreaterThan(0);
      for (const path of matches) {
        expect(ALLOWED_PATHS.has(topLevel(path))).toBe(true);
      }
    }
  });
});

describe("No direct HTTP / no domain access", () => {
  it("pages, components, state and layouts never call fetch/axios directly", () => {
    for (const dir of ["pages", "components", "state", "layouts"]) {
      const full = join(SRC, dir);
      if (!existsSync(full)) continue;
      for (const file of readdirSync(full)) {
        if (!/\.tsx?$/.test(file)) continue;
        const content = readFileSync(join(full, file), "utf8");
        expect(content).not.toMatch(/\bfetch\s*\(/);
        expect(content).not.toMatch(/\baxios\b/);
      }
    }
  });

  it("the frontend has no reference to domain internals", () => {
    // Only actual domain component names are forbidden; user-facing labels like
    // "Merge" (a UI concept) are allowed.
    const forbidden = /\b(WorkMatcher|WorkGroupingMatcher|DefaultWorkMatcher|DefaultWorkRanker|MergeEngine|DefaultMergeService|EvidenceCollector|KnowledgeCollector|KnowledgeMiner)\b/;
    for (const dir of ["pages", "components", "state", "layouts", "api"]) {
      const full = join(SRC, dir);
      if (!existsSync(full)) continue;
      for (const file of readdirSync(full)) {
        if (!/\.tsx?$/.test(file)) continue;
        const content = readFileSync(join(full, file), "utf8");
        expect(content).not.toMatch(forbidden);
      }
    }
  });
});
