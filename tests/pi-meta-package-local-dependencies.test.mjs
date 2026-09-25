import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { readJson, ROOT } from "./helpers.mjs";

const META_PACKAGE = join(ROOT, "consult");

function readPackage(packageDir) {
  return readJson(join(packageDir, "package.json"));
}

describe("Pi single-package layout", () => {
  it("makes the repo root installable from GitHub with only the bundled Consult package surface", () => {
    const pkg = readPackage(ROOT);

    expect(pkg.private).toBe(true);
    expect(pkg.name).toBe("consult-github");
    expect(pkg.pi.extensions).toEqual(["./consult/src/index.ts"]);
    expect(pkg.pi.skills).toEqual(["./consult/skills"]);
    expect(pkg.files).toEqual([
      "consult/src",
      "consult/extensions",
      "consult/skills",
      "consult/README.md",
      "consult/LICENSE",
      "README.md",
      "LICENSE",
    ]);
    expect(pkg.files.some((path) => path.includes("node_modules"))).toBe(false);
  });

  it("publishes the scoped Pi package without bundled host dependencies", () => {
    const pkg = readPackage(META_PACKAGE);

    expect(pkg.name).toBe("@kreek/consult");
    expect(pkg.version).toBe("15.2.0");
    expect(pkg.engines.node).toBe(">=22.19.0");
    expect(pkg.pi.extensions).toEqual(["./src/index.ts"]);
    expect(pkg.pi.skills).toEqual(["./skills"]);
    expect(pkg.dependencies).toBeUndefined();
    expect(pkg.bundledDependencies).toBeUndefined();
    expect(pkg.peerDependencies).toMatchObject({
      "@earendil-works/pi-ai": "*",
      "@earendil-works/pi-coding-agent": "*",
      "@earendil-works/pi-tui": "*",
      typebox: "*",
    });
    expect(pkg.files).toEqual(["src", "extensions", "skills", "README.md", "LICENSE"]);
  });

  it("type-checks and tests the current Pi runtime", () => {
    const pkg = readPackage(META_PACKAGE);

    expect(pkg.pi.extensions).toEqual(["./src/index.ts"]);
    expect(pkg.scripts.test).toBe("vitest run test");
    expect(pkg.scripts.typecheck).toBe("tsc --noEmit");
  });
});
