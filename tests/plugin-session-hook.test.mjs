// End-to-end check of the shipped SessionStart hook: run its command the way a
// host does and compare the output with the workflow skill's core.md source.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { HOOK_DEST, HOOK_SOURCE } from "../scripts/generate-plugin-symlinks.mjs";
import { ROOT, run } from "./helpers.mjs";

// The routing paragraph comes first so it survives if a host truncates hook
// output; keeping it short keeps that guarantee cheap.
const MAX_ROUTING_CHARS = 400;

function sessionStartCommand() {
  const hooksFile = JSON.parse(readFileSync(join(ROOT, HOOK_DEST), "utf8"));
  return hooksFile.hooks.SessionStart[0].hooks[0].command;
}

describe("plugin SessionStart hook", () => {
  const result = run("sh", ["-c", sessionStartCommand()]);
  const printed = result.stdout.trim();

  it("prints the workflow skill's core.md exactly, ending in one newline", () => {
    const core = readFileSync(join(ROOT, HOOK_SOURCE), "utf8").replaceAll("\r", "").trim();
    expect(result.status).toBe(0);
    expect(result.stdout).toBe(`${core}\n`);
  });

  it("opens with a short routing paragraph that names a skill the plugin ships", () => {
    const routing = printed.split("\n\n")[0];
    // eval/scripts/triggers.py detects the hook by this phrase.
    expect(routing.startsWith("Consult is installed.")).toBe(true);
    expect(routing.length).toBeLessThanOrEqual(MAX_ROUTING_CHARS);
    const named = routing.match(/consult:([a-z][a-z0-9-]*) skill/)?.[1];
    expect(named, "routing paragraph names no Consult skill").toBeDefined();
    expect(existsSync(join(ROOT, "plugin/skills", named, "SKILL.md"))).toBe(true);
  });
});
