#!/usr/bin/env node
// Run deterministic Consult pre-commit checks for staged diffs and Markdown changes.

import { spawnSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export class Check {
  constructor(reason, command, requiredTools = []) {
    this.reason = reason;
    this.command = command;
    this.requiredTools = requiredTools;
  }
}

export function repoRootFromScript() {
  return resolve(dirname(fileURLToPath(import.meta.url)), "..");
}

export function runGit(root, ...args) {
  return spawnSync("git", args, { cwd: root, encoding: "utf8" });
}

export function currentBranch(root) {
  const result = runGit(root, "branch", "--show-current");
  return result.status === 0 ? result.stdout.trim() : "";
}

export function stagedPaths(root) {
  const result = runGit(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRD");
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || "could not inspect staged files");
  }
  return result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function hasAny(paths, predicate) {
  return paths.some(predicate);
}

function commandExists(command) {
  const result = spawnSync("sh", ["-c", `command -v ${command} >/dev/null 2>&1`]);
  return result.status === 0;
}

export function selectChecks(paths) {
  const checks = [new Check("staged diff has no whitespace errors", ["git", "diff", "--cached", "--check"])];

  if (hasAny(paths, (path) => path.endsWith(".md"))) {
    checks.push(new Check("Markdown parses and local links resolve", ["pnpm", "run", "check:links"], ["pnpm"]));
  }

  return checks;
}

export function formatCommand(command) {
  return command.join(" ");
}

export function missingTools(check) {
  return check.requiredTools.filter((tool) => !commandExists(tool));
}

export function runChecks(root, checks, dryRun) {
  let failures = 0;
  for (const check of checks) {
    const command = formatCommand(check.command);
    console.log(`==> ${command}`);
    console.log(`    ${check.reason}`);

    const missing = missingTools(check);
    if (missing.length > 0) {
      console.error(`ERROR: missing required tool(s): ${missing.join(", ")}`);
      failures += 1;
      continue;
    }

    if (dryRun) continue;

    const [program, ...args] = check.command;
    const result = spawnSync(program, args, { cwd: root, stdio: "inherit" });
    if (result.status !== 0) {
      console.error(`ERROR: command failed with exit code ${result.status}`);
      failures += 1;
    }
  }
  return failures ? 1 : 0;
}

function parseArgs(argv) {
  let repoRoot = repoRootFromScript();
  let dryRun = false;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "-h" || arg === "--help") {
      console.log(`Usage: node scripts/pre-commit-acceptance.mjs [--repo-root PATH] [--dry-run]

Run Consult pre-commit checks for staged files.`);
      return { help: true };
    } else if (arg === "--dry-run") {
      dryRun = true;
    } else if (arg === "--repo-root") {
      repoRoot = argv[index + 1];
      index += 1;
    } else {
      console.error(`ERROR: unknown option: ${arg}`);
      return { error: true };
    }
  }
  return { repoRoot: resolve(repoRoot), dryRun };
}

export function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) return 0;
  if (args.error) return 2;

  const root = args.repoRoot;
  if (!existsSync(root) || !statSync(root).isDirectory()) {
    console.error(`ERROR: repo root is not a directory: ${root}`);
    return 2;
  }

  const branch = currentBranch(root);

  let paths;
  try {
    paths = stagedPaths(root);
  } catch (error) {
    console.error(`ERROR: ${error.message}`);
    return 2;
  }

  if (paths.length === 0) {
    console.log("No staged files; nothing to validate.");
    return 0;
  }

  console.log("Consult pre-commit checks");
  console.log(`Branch: ${branch || "(detached HEAD)"}`);
  console.log("Staged files:");
  for (const path of paths) console.log(`  - ${path}`);

  return runChecks(root, selectChecks(paths), args.dryRun);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = main();
}
