#!/usr/bin/env node
// Sync plugin copies from canonical agent assets: the plugin/skills mirror and
// the SessionStart hook in plugin/hooks/hooks.json. validate-skill-anatomy.mjs
// imports the exports below to check that neither has drifted.

import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
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

// The SessionStart hook prints the Consult core. Its text lives in the workflow
// skill, so it also ships in the plugin/skills mirror for readers that never
// run the hook. hooks.json carries the text inline rather than reading a path,
// because the eval passes only hooks.json to Claude Code, and Codex has
// resolved plugin root placeholders differently from Claude Code. The heredoc
// needs a POSIX sh, which is how Claude Code runs hook commands.
export const HOOK_SOURCE = "agents/.agents/skills/workflow/references/core.md";
export const HOOK_DEST = "plugin/hooks/hooks.json";
// Every session pays for the hook text, and hosts cap hook output (Claude Code
// at 10,000 characters), so the core stays well below that.
export const MAX_HOOK_CHARS = 4000;
const HEREDOC_END = "CONSULT_CORE";

function hookText(markdown) {
  return markdown.replaceAll("\r", "").trim();
}

/**
 * Says why `markdown` cannot become the hook text.
 * @param {string} markdown - contents of HOOK_SOURCE
 * @returns {string | null} a problem phrased to follow the file name, or null
 */
export function hookSourceProblem(markdown) {
  const text = hookText(markdown);
  if (!text) return "is empty";
  if (text.length > MAX_HOOK_CHARS) {
    return `is ${text.length} characters; the SessionStart hook allows ${MAX_HOOK_CHARS}`;
  }
  if (text.split("\n").includes(HEREDOC_END)) {
    return `has a line equal to ${HEREDOC_END}, which would end the hook's heredoc`;
  }
  return null;
}

/**
 * Renders hooks.json: one SessionStart command that prints `markdown` through
 * a quoted heredoc, so the shell expands nothing in it.
 * @param {string} markdown - contents of HOOK_SOURCE; check hookSourceProblem first
 * @returns {string} the full hooks.json text, newline-terminated
 */
export function renderSessionStartHooks(markdown) {
  const command = `cat <<'${HEREDOC_END}'\n${hookText(markdown)}\n${HEREDOC_END}`;
  const hooks = { hooks: { SessionStart: [{ hooks: [{ type: "command", command }] }] } };
  return `${JSON.stringify(hooks, null, 2)}\n`;
}

// A root without the hook source (a test fixture, say) keeps whatever hooks.json
// it has; the validator reports a missing source in the real repo.
function syncSessionStartHook(root) {
  const source = resolve(root, HOOK_SOURCE);
  if (!existsSync(source)) {
    console.log(`no ${HOOK_SOURCE}; left ${HOOK_DEST} unchanged`);
    return 0;
  }
  const markdown = readFileSync(source, "utf8");
  const problem = hookSourceProblem(markdown);
  if (problem) {
    console.error(`ERROR: ${HOOK_SOURCE} ${problem}`);
    return 1;
  }
  mkdirSync(resolve(root, dirname(HOOK_DEST)), { recursive: true });
  writeFileSync(resolve(root, HOOK_DEST), renderSessionStartHooks(markdown), "utf8");
  console.log(`generated ${HOOK_DEST} from ${HOOK_SOURCE}`);
  return 0;
}

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
  return syncSessionStartHook(root);
}

export function main(argv = process.argv.slice(2)) {
  if (argv.includes("-h") || argv.includes("--help")) {
    console.log(`Usage: node scripts/generate-plugin-symlinks.mjs [repo_root]

Sync every skill mirror (plugin/skills) from agents/.agents/skills, and
generate plugin/hooks/hooks.json from the workflow skill's references/core.md.`);
    return 0;
  }
  const repoRoot = argv[0] ?? repoRootFromScript();
  return syncPluginSymlinks(repoRoot);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = main();
}
