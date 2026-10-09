import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { cleanupTempDir, makeTempDir, ROOT, run, writeExecutable } from "./helpers.mjs";

const SCRIPT = join(ROOT, "scripts/update-installed-plugins.sh");
let tmp;

function makeFakeAgentBin(home) {
  const bin = join(home, "bin");
  mkdirSync(bin, { recursive: true });

  for (const name of ["claude", "codex", "pi", "agy", "cursor"]) {
    writeExecutable(
      join(bin, name),
      `#!/bin/sh
set -eu
printf '%s %s\\n' "${name}" "$*" >> "$HOME/agent-plugin-updates.log"
`,
    );
  }

  return bin;
}

describe("update-installed-plugins.sh", () => {
  afterEach(() => {
    if (tmp) cleanupTempDir(tmp);
    tmp = undefined;
  });

  it("prints official agent-harness update commands in dry-run mode", () => {
    tmp = makeTempDir();
    const bin = makeFakeAgentBin(tmp);

    const result = run("/bin/bash", [SCRIPT, "--dry-run"], {
      cwd: ROOT,
      env: { ...process.env, HOME: tmp, PATH: `${bin}:/usr/bin:/bin` },
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("claude plugin marketplace add dawson-design/consult");
    expect(result.stdout).toContain("claude plugin install consult@consult");
    expect(result.stdout).toContain("claude plugin update consult@consult");
    expect(result.stdout).toContain("codex plugin marketplace add dawson-design/consult");
    expect(result.stdout).toContain("codex plugin marketplace upgrade consult");
    expect(result.stdout).toContain("codex plugin add consult@consult");
    expect(result.stdout).not.toContain("pi install");
    expect(result.stdout).toContain("agy plugin install");
    expect(result.stdout).toContain("cursor agent --print");
    expect(result.stdout).not.toContain("cp -R");
    expect(existsSync(join(tmp, "agent-plugin-updates.log"))).toBe(false);
  });

  it("runs plugin update commands through installed agent CLIs", () => {
    tmp = makeTempDir();
    const bin = makeFakeAgentBin(tmp);

    const result = run("/bin/bash", [SCRIPT], {
      cwd: ROOT,
      env: { ...process.env, HOME: tmp, PATH: `${bin}:/usr/bin:/bin` },
    });

    expect(result.status).toBe(0);
    const log = readFileSync(join(tmp, "agent-plugin-updates.log"), "utf8");
    expect(log).toContain("claude plugin marketplace add dawson-design/consult");
    expect(log).toContain("claude plugin marketplace update consult");
    expect(log).toContain("claude plugin install consult@consult");
    expect(log).toContain("claude plugin update consult@consult");
    expect(log).toContain("codex plugin marketplace add dawson-design/consult");
    expect(log).toContain("codex plugin marketplace upgrade consult");
    expect(log).toContain("codex plugin add consult@consult");
    expect(log).not.toContain("pi install");
    expect(log).toContain(`agy plugin install ${join(ROOT, "plugin")}`);
    expect(log).toContain("cursor agent --print Update the Consult plugin");
  });
});
