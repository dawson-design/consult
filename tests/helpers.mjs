import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));

export function makeTempDir(prefix = "has-test-") {
  return mkdtempSync(join(tmpdir(), prefix));
}

export function cleanupTempDir(path) {
  rmSync(path, { recursive: true, force: true });
}

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? ROOT,
    env: options.env ?? process.env,
    encoding: "utf8",
    input: options.input,
    shell: false,
  });

  // A missing binary yields `status: null` with the reason tucked into `error`.
  // Swallowing that turns "expect is not installed" into an assertion failure on
  // an exit code, which is how four failing tests got misattributed to `stow`.
  if (result.error) {
    throw new Error(`failed to spawn ${command}: ${result.error.message}`, { cause: result.error });
  }

  return result;
}

/** True when `command` resolves on PATH. Use with `it.skipIf` to guard tests
 * that need an external binary, so a missing tool skips loudly instead of
 * failing as if the code under test were broken. */
export function commandExists(command) {
  const probe = spawnSync("sh", ["-c", `command -v ${command} >/dev/null 2>&1`]);
  return probe.status === 0;
}

export function writeExecutable(path, text) {
  writeFileSync(path, text, "utf8");
  chmodSync(path, 0o755);
}
