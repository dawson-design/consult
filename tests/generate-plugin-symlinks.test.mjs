import { existsSync, mkdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { cleanupTempDir, makeTempDir, ROOT, run } from "./helpers.mjs";
import { HOOK_DEST, HOOK_SOURCE, MAX_HOOK_CHARS, MIRROR_DESTS } from "../scripts/generate-plugin-symlinks.mjs";

const SCRIPT = join(ROOT, "scripts/generate-plugin-symlinks.mjs");
let tmp;

function makeSkill(root, name) {
  const skill = join(root, "agents/.agents/skills", name);
  mkdirSync(skill, { recursive: true });
  writeFileSync(join(skill, "SKILL.md"), `# ${name}\n`, "utf8");
  return skill;
}

function writeCore(root, text) {
  mkdirSync(join(root, HOOK_SOURCE, ".."), { recursive: true });
  writeFileSync(join(root, HOOK_SOURCE), text, "utf8");
}

function hookCommand(root) {
  return JSON.parse(readFileSync(join(root, HOOK_DEST), "utf8")).hooks.SessionStart[0].hooks[0].command;
}

function runScript(...args) {
  return run("node", [SCRIPT, ...args], { cwd: ROOT });
}

describe("generate-plugin-symlinks CLI", () => {
  afterEach(() => {
    if (tmp) cleanupTempDir(tmp);
    tmp = undefined;
  });

  it("writes every declared mirror destination", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "code-review");

    const result = runScript(tmp);

    expect(result.status).toBe(0);
    const canonical = readFileSync(join(tmp, "agents/.agents/skills/code-review/SKILL.md"), "utf8");
    // Guards against a destination being dropped from MIRROR_DESTS: losing one
    // would otherwise only surface later, as drift on the next canonical edit.
    expect(MIRROR_DESTS).toEqual(["plugin/skills"]);
    for (const dest of MIRROR_DESTS) {
      expect(readFileSync(join(tmp, dest, "code-review/SKILL.md"), "utf8")).toBe(canonical);
    }
  });

  it("creates real plugin copies for skills", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "code-review");

    const result = runScript(tmp);

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("plugin skill mirror in sync");
    const copy = join(tmp, "plugin/skills/code-review");
    expect(readFileSync(join(copy, "SKILL.md"), "utf8")).toBe(
      readFileSync(join(tmp, "agents/.agents/skills/code-review/SKILL.md"), "utf8"),
    );
  });

  it("removes stale generated entries without removing real files", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "code-review");
    const pluginSkills = join(tmp, "plugin/skills");
    mkdirSync(pluginSkills, { recursive: true });
    symlinkSync("../../agents/.agents/skills/old", join(pluginSkills, "old"));
    writeFileSync(join(pluginSkills, "local-note"), "keep me\n", "utf8");

    const result = runScript(tmp);

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("removed stale plugin entry: plugin/skills/old");
    expect(result.stderr).toContain("plugin/skills/local-note is not a generated directory");
    expect(readFileSync(join(pluginSkills, "local-note"), "utf8")).toBe("keep me\n");
  });

  it("refuses to overwrite real plugin entries", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "code-review");
    const pluginSkills = join(tmp, "plugin/skills");
    mkdirSync(pluginSkills, { recursive: true });
    const conflict = join(pluginSkills, "code-review");
    writeFileSync(conflict, "not a symlink\n", "utf8");

    const result = runScript(tmp);

    expect(result.status).toBe(1);
    expect(readFileSync(conflict, "utf8")).toBe("not a symlink\n");
    expect(result.stderr).toContain("plugin/skills/code-review exists as a real file/dir");
  });

  it("generates a SessionStart hook that prints core.md without shell expansion", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "workflow");
    const core = "Consult is installed.\r\n\nKeep `$HOME`, \"quotes\", 'apostrophes', and \\n literal.\n";
    writeCore(tmp, core);

    const result = runScript(tmp);

    expect(result.status).toBe(0);
    expect(result.stdout).toContain(`generated ${HOOK_DEST} from ${HOOK_SOURCE}`);
    const printed = run("sh", ["-c", hookCommand(tmp)], { cwd: tmp });
    expect(printed.status).toBe(0);
    expect(printed.stdout).toBe("Consult is installed.\n\nKeep `$HOME`, \"quotes\", 'apostrophes', and \\n literal.\n");
  });

  it.each([
    ["has a line that would end the heredoc", "Consult is installed.\nCONSULT_CORE\nmore\n", "has a line equal to CONSULT_CORE"],
    ["is longer than the hook allows", `Consult is installed. ${"x".repeat(MAX_HOOK_CHARS)}\n`, "the SessionStart hook allows"],
    ["is empty", "  \n", "is empty"],
  ])("refuses a core.md that %s and writes no hook", (_label, core, message) => {
    tmp = makeTempDir();
    makeSkill(tmp, "workflow");
    writeCore(tmp, core);

    const result = runScript(tmp);

    expect(result.status).toBe(1);
    expect(result.stderr).toContain(message);
    expect(existsSync(join(tmp, HOOK_DEST))).toBe(false);
  });

  it("leaves the hooks file alone when core.md is absent", () => {
    tmp = makeTempDir();
    makeSkill(tmp, "code-review");

    const result = runScript(tmp);

    expect(result.status).toBe(0);
    expect(result.stdout).toContain(`no ${HOOK_SOURCE}; left ${HOOK_DEST} unchanged`);
    expect(existsSync(join(tmp, HOOK_DEST))).toBe(false);
  });

  it("rejects paths that are not repo roots", () => {
    tmp = makeTempDir();

    const result = runScript(tmp);

    expect(result.status).toBe(2);
    expect(result.stderr).toContain("not a repo root");
  });
});
