import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ROOT, run } from "./helpers.mjs";

// Every host adds this output to each session's context, so it stays small.
const MAX_ROUTING_CHARS = 400;

function sessionStartCommand() {
  const hooksFile = JSON.parse(readFileSync(join(ROOT, "plugin/hooks/hooks.json"), "utf8"));
  return hooksFile.hooks.SessionStart[0].hooks[0].command;
}

describe("plugin SessionStart hook", () => {
  it("prints a short routing line that names a skill the plugin ships", () => {
    const result = run("sh", ["-c", sessionStartCommand()]);

    expect(result.status).toBe(0);
    const routing = result.stdout.trim();
    expect(routing.length).toBeGreaterThan(0);
    expect(routing.length).toBeLessThanOrEqual(MAX_ROUTING_CHARS);
    const named = routing.match(/consult:([a-z][a-z0-9-]*) skill/)?.[1];
    expect(named, "routing line names no Consult skill").toBeDefined();
    expect(existsSync(join(ROOT, "plugin/skills", named, "SKILL.md"))).toBe(true);
  });
});
