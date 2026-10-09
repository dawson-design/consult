#!/usr/bin/env node
// Sync plugin copies from canonical agent assets.

import { cpSync, existsSync, lstatSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function repoRootFromScript() {
  return resolve(dirname(fileURLToPath(import.meta.url)), "..");
}

function pathExists(path) {
  try {
    lstatSync(path);
    return true;
  } catch {
    return false;
  }
}

function display(path, root) {
  const rel = relative(root, path);
  return rel && !rel.startsWith("..") ? rel : path;
}

function pruneDest(dest, src, root) {
  if (!existsSync(dest)) return;

  for (const name of readdirSync(dest).sort()) {
    const entry = resolve(dest, name);
    if (!pathExists(entry)) continue;
    if (existsSync(resolve(src, name))) continue;

    const stat = lstatSync(entry);
    if (stat.isSymbolicLink() || stat.isDirectory()) {
      rmSync(entry, { recursive: true, force: true });
      console.log(`removed stale plugin entry: ${display(entry, root)}`);
      continue;
    }

    console.error(`WARNING: ${display(entry, root)} is not a generated directory; leaving in place`);
  }
}

function syncEach(src, dest, root) {
  for (const name of readdirSync(src).sort()) {
    const entry = resolve(src, name);
    if (!pathExists(entry)) continue;

    const target = resolve(dest, name);
    if (pathExists(target)) {
      const stat = lstatSync(target);
      if (stat.isSymbolicLink() || stat.isDirectory()) {
        rmSync(target, { recursive: true, force: true });
      } else {
        console.error(`ERROR: ${display(target, root)} exists as a real file/dir; remove it first`);
        return 1;
      }
    }

    cpSync(entry, target, { recursive: true, verbatimSymlinks: true });
    console.log(`copied ${display(entry, root)} -> ${display(target, root)}`);
  }
  return 0;
}

// Every committed copy of the canonical skills. Each is regenerated from
// agents/.agents/skills so no mirror can silently drift.
export const MIRROR_DESTS = ["plugin/skills"];

export function syncPluginSymlinks(repoRoot = repoRootFromScript()) {
  const root = resolve(repoRoot);
  const skillsSrc = resolve(root, "agents/.agents/skills");

  if (!existsSync(skillsSrc) || !lstatSync(skillsSrc).isDirectory()) {
    console.error(`not a repo root (no agents/.agents/skills): ${root}`);
    return 2;
  }

  for (const dest of MIRROR_DESTS) {
    const skillsDest = resolve(root, dest);
    mkdirSync(skillsDest, { recursive: true });
    pruneDest(skillsDest, skillsSrc, root);

    const result = syncEach(skillsSrc, skillsDest, root);
    if (result !== 0) return result;
  }

  console.log("plugin skill mirror in sync");
  return 0;
}

export function main(argv = process.argv.slice(2)) {
  if (argv.includes("-h") || argv.includes("--help")) {
    console.log(`Usage: node scripts/generate-plugin-symlinks.mjs [repo_root]

Sync every skill mirror (plugin/skills) from agents/.agents/skills.`);
    return 0;
  }
  const repoRoot = argv[0] ?? repoRootFromScript();
  return syncPluginSymlinks(repoRoot);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = main();
}
