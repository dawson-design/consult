import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { cleanupTempDir, makeTempDir, ROOT, run } from "./helpers.mjs";
import { formatCommand, selectChecks } from "../scripts/pre-commit-acceptance.mjs";

const SCRIPT = join(ROOT, "scripts/pre-commit-acceptance.mjs");
let tmp;

function commandStrings(paths) {
  return selectChecks(paths).map((check) => formatCommand(check.command));
}

function runScript(...args) {
  return run("node", [SCRIPT, ...args], { cwd: ROOT });
}

describe("pre-commit acceptance command selection", () => {
  it("always checks the staged diff", () => {
    expect(commandStrings(["README.md"])).toContain("git diff --cached --check");
  });

  it("checks Markdown when Markdown files are staged", () => {
    expect(commandStrings(["README.md"])).toContain("pnpm run check:links");
  });
});

describe("pre-commit acceptance CLI", () => {
  afterEach(() => {
    if (tmp) cleanupTempDir(tmp);
    tmp = undefined;
  });

  it("allows dry-run checks on main", () => {
    tmp = makeTempDir();
    run("git", ["init", "-b", "main"], { cwd: tmp });

    const result = runScript("--repo-root", tmp, "--dry-run");

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("No staged files; nothing to validate.");
  });

  it("reports no staged files on topic branches", () => {
    tmp = makeTempDir();
    mkdirSync(join(tmp, "repo"), { recursive: true });
    run("git", ["init", "-b", "chore/test"], { cwd: tmp });

    const result = runScript("--repo-root", tmp, "--dry-run");

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("No staged files; nothing to validate.");
  });
});
