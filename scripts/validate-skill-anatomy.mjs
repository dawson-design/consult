#!/usr/bin/env node
// Validate Consult skill files and plugin mirror drift.

import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { MIRROR_DESTS } from "./generate-plugin-symlinks.mjs";

const REQUIRED_SECTIONS = ["When to Use", "When NOT to Use", "Rules"];
// Retired by the Rules-section anatomy. A skill that still carries one of
// these restates its rules; the validator rejects it.
const OBSOLETE_RULE_SECTIONS = ["Core Ideas", "Verification", "Before Saying Done"];
// A SKILL.md is steering context, not a book. The budget is the regression
// guard for the knowledge-vs-policy trim: rules the model cannot derive fit
// in this space; explanations of standard practice do not.
const MAX_BODY_WORDS = 700;
// Raised budgets, each with a reason. workflow carries the validator-mandated
// 24-row routing table (~215 words) plus the sign-off table. workflow,
// code-review, and proof also absorbed the 12.1.0 host-harness and 13.1.0
// fresh-context-review policy, which is rule text, not explanation. workflow
// rose to 1,120 for the plan-handoff rule, which lets a cheaper model build
// from a plan a stronger model wrote, and to 1,135 for the issue-tracking
// routing row the router cross-check requires.
const BODY_WORD_EXCEPTIONS = { workflow: 1135, proof: 950, "code-review": 950 };
const MAX_TRIPWIRE_ROWS = 8;
const MAX_DESCRIPTION_LENGTH = 120;
// ~600 tokens of routing surface that every host loads before picking a skill.
// Chosen deliberately once the measurement was honest: the previous 2,000 was
// never enforced (descriptions were truncated at their first inner colon), and
// the pack turned out to be at 2,069 the whole time. 2,400 left room for about
// four more skills. issue-tracking brought the pack to 2,399, so the next skill
// needs keyword cuts elsewhere or a stated reason to raise this.
const MAX_TOTAL_DESCRIPTION_LENGTH = 2400;

const NAME_RE = /^name:\s+[a-z][a-z0-9-]*\s*$/m;
const ATTRIBUTION_RE = /\b[Pp]er\s+(?:[A-Z][a-z]+\s+)?[A-Z][a-z]+\b/;
const EM_DASH = "—";
// One authoritative phrasing of the direction-vs-shapes approval rule. Skills
// that invoke the concept must carry this sentence verbatim so the semantics
// cannot drift file by file.
const APPROVAL_CONCEPT_RE = /approving design or RFC/i;
const CANONICAL_APPROVAL_SENTENCE =
  "An approving design or RFC approves the direction, not the concrete shapes";
const TRIPWIRES_TABLE_HEADER_RE = /^\|\s*Trigger\s*\|\s*Do this instead\s*\|\s*False alarm\s*\|/m;
function scriptDir() {
  return dirname(fileURLToPath(import.meta.url));
}

function defaultSkillsDir() {
  return resolve(scriptDir(), "../agents/.agents/skills");
}

function sectionRe(name) {
  return new RegExp(`^##+\\s+${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "m");
}

function skillSections(body) {
  const lines = body.split(/\r?\n/);
  const headings = lines
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => /^##\s+/.test(line));

  return headings.map(({ line, index }, headingIndex) => {
    const next = headings[headingIndex + 1]?.index ?? lines.length;
    return { name: line.replace(/^##\s+/, "").trim(), lineCount: next - index - 1 };
  });
}

function tripwireRowCount(body) {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((line) => /^##\s+Tripwires\s*$/.test(line));
  if (start === -1) return 0;
  let rows = 0;
  for (const line of lines.slice(start + 1)) {
    if (/^##\s+/.test(line)) break;
    if (/^\|\s*"/.test(line)) rows += 1;
  }
  return rows;
}

// Numbers of the top-level rules in `## Rules`, up to the first `##` or `###`.
// Rule ids (`<skill>.<n>`) key the eval's rule checks in eval/verifier/rules.json.
export function ruleNumbers(body) {
  const lines = body.split(/\r?\n/);
  const start = lines.findIndex((line) => /^##\s+Rules\s*$/.test(line));
  if (start === -1) return [];
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((line) => /^###?\s+/.test(line));
  return (end === -1 ? rest : rest.slice(0, end))
    .map((line) => line.match(/^(\d+)\.\s/)?.[1])
    .filter(Boolean)
    .map(Number);
}

function bodyWordCount(body) {
  const withoutFrontmatter = body.replace(/^---[\s\S]*?\n---\n/, "");
  // Count words, not table plumbing: pipes and separator rows cost almost nothing.
  return withoutFrontmatter.split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token)).length;
}

function skillName(head) {
  return head.match(/^name:\s+(\S+)/m)?.[1] ?? "";
}

function bodyWithoutReferenceSections(body) {
  const kept = [];
  let inReferenceSection = false;
  for (const line of body.split(/\r?\n/)) {
    if (/^##+ (References|Canon)\s*$/.test(line)) {
      inReferenceSection = true;
      continue;
    }
    if (!inReferenceSection) kept.push(line);
  }
  return kept.join("\n");
}

export function frontmatterDescription(head) {
  const lines = head.split(/\r?\n/);
  const description = [];
  let inDescription = false;

  for (const line of lines) {
    if (line.startsWith("description:")) {
      inDescription = true;
      const value = line.slice("description:".length).trim();
      if (value && !new Set([">", ">-", "|", "|-"]).has(value)) {
        description.push(value);
      }
      continue;
    }

    if (inDescription) {
      if (line.startsWith("  ")) {
        description.push(line.trim());
        continue;
      }
      break;
    }
  }

  if (!inDescription) return null;
  return unquoteScalar(description.join(" "));
}

// A quoted YAML scalar's delimiters are syntax, not description text. Strip
// them so the length budgets measure what an agent actually reads.
function unquoteScalar(value) {
  for (const quote of ['"', "'"]) {
    if (value.length >= 2 && value.startsWith(quote) && value.endsWith(quote)) {
      return value.slice(1, -1);
    }
  }
  return value;
}

export function validateSkillFile(path) {
  const body = readFileSync(path, "utf8");
  const head = body.split(/\r?\n/).slice(0, 30).join("\n");
  const problems = [];

  if (!NAME_RE.test(head)) problems.push("frontmatter missing name or not kebab-case");
  const description = frontmatterDescription(head);
  if (description == null) {
    problems.push("frontmatter missing description");
  } else if (description.length > MAX_DESCRIPTION_LENGTH) {
    problems.push(`frontmatter description too long (${description.length} > ${MAX_DESCRIPTION_LENGTH} characters)`);
  }

  for (const heading of REQUIRED_SECTIONS) {
    if (!sectionRe(heading).test(body)) problems.push(`missing section: ## ${heading}`);
  }
  for (const heading of OBSOLETE_RULE_SECTIONS) {
    if (sectionRe(heading).test(body)) problems.push(`obsolete section: ## ${heading} -- state the rule once under ## Rules`);
  }
  const words = bodyWordCount(body);
  const budget = BODY_WORD_EXCEPTIONS[skillName(head)] ?? MAX_BODY_WORDS;
  if (words > budget) problems.push(`body too long (${words} > ${budget} words) -- keep policy, drop explanation`);

  if (sectionRe("Common Rationalizations").test(body)) {
    problems.push("obsolete section: ## Common Rationalizations -- use ## Tripwires");
  }
  if (sectionRe("Red Flags").test(body)) {
    problems.push("obsolete section: ## Red Flags -- fold into ## Tripwires");
  }
  if (/^\|\s*Excuse\s*\|\s*Reality\s*\|/m.test(body)) {
    problems.push("obsolete table header: use the '| Trigger | Do this instead | False alarm |' Tripwires table");
  }
  if (sectionRe("Tripwires").test(body) && !TRIPWIRES_TABLE_HEADER_RE.test(body)) {
    problems.push("Tripwires must use the '| Trigger | Do this instead | False alarm |' table format");
  }
  const tripwireRows = tripwireRowCount(body);
  if (tripwireRows > MAX_TRIPWIRE_ROWS) {
    problems.push(`Tripwires has ${tripwireRows} rows (max ${MAX_TRIPWIRE_ROWS}) -- keep only high-probability failure moments`);
  }

  if (body.includes(EM_DASH)) {
    problems.push("em dash found -- use a period, colon, comma, or parentheses instead");
  }

  const flattened = body.replace(/\s+/g, " ");
  if (APPROVAL_CONCEPT_RE.test(flattened) && !flattened.includes(CANONICAL_APPROVAL_SENTENCE)) {
    problems.push(
      `'approving design or RFC' used without the canonical sentence: "${CANONICAL_APPROVAL_SENTENCE}"`,
    );
  }

  const attributionLines = bodyWithoutReferenceSections(body)
    .split(/\r?\n/)
    .filter((line) => !line.startsWith(">") && ATTRIBUTION_RE.test(line));
  if (attributionLines.length > 0) {
    problems.push("inline 'per <expert>' attribution found -- move to References");
  }

  return problems.length > 0 ? { path, problems } : null;
}

export function validateSkillReferences(skillDir) {
  const referencesDir = join(skillDir, "references");
  const findings = [];
  for (const path of walkFiles(referencesDir)) {
    if (!path.endsWith(".md")) continue;
    if (readFileSync(path, "utf8").includes(EM_DASH)) {
      findings.push({
        path,
        problems: ["em dash found -- use a period, colon, comma, or parentheses instead"],
      });
    }
  }
  return findings;
}

// The workflow skill's tables route to every other skill. Cross-check both
// directions so the router and the skill set cannot drift apart: every
// backticked name in a workflow table row must be a real skill, and every
// skill must be reachable from the workflow body.
export function validateWorkflowRouting(skillsDir) {
  const workflowFile = join(skillsDir, "workflow", "SKILL.md");
  if (!existsSync(workflowFile)) return [];

  const body = readFileSync(workflowFile, "utf8");
  const problems = [];
  const skillNames = readdirSync(skillsDir)
    .sort()
    .filter((name) => existsSync(join(skillsDir, name, "SKILL.md")));

  const routedNames = [...body.matchAll(/^\s*\|\s*`([a-z][a-z0-9-]*)`\s*\|/gm)].map((match) => match[1]);
  for (const name of routedNames) {
    if (!skillNames.includes(name)) {
      problems.push(`routing table names '${name}' but no such skill exists`);
    }
  }

  for (const name of skillNames) {
    if (name === "workflow") continue;
    if (!body.includes(`\`${name}\``)) {
      problems.push(`skill '${name}' is not referenced by the workflow router`);
    }
  }

  return problems.length > 0 ? [{ path: workflowFile, problems }] : [];
}

export function validateSkills(skillsDir) {
  const findings = [];
  let totalDescriptionLength = 0;

  for (const name of readdirSync(skillsDir).sort()) {
    const skillFile = join(skillsDir, name, "SKILL.md");
    if (!existsSync(skillFile)) continue;
    const body = readFileSync(skillFile, "utf8");
    const head = body.split(/\r?\n/).slice(0, 30).join("\n");
    const description = frontmatterDescription(head);
    if (description != null) totalDescriptionLength += description.length;

    const finding = validateSkillFile(skillFile);
    if (finding) findings.push(finding);
    findings.push(...validateSkillReferences(join(skillsDir, name)));
  }

  findings.push(...validateWorkflowRouting(skillsDir));

  if (totalDescriptionLength > MAX_TOTAL_DESCRIPTION_LENGTH) {
    findings.push({
      path: join(skillsDir, "SKILL_DESCRIPTIONS"),
      problems: [
        `frontmatter description total too long (${totalDescriptionLength} > ${MAX_TOTAL_DESCRIPTION_LENGTH} characters)`,
      ],
    });
  }

  return findings;
}

export function printSkillFindings(skillsDir, findings) {
  for (const finding of findings) {
    console.log(relative(skillsDir, finding.path));
    for (const problem of finding.problems) console.log(`  - ${problem}`);
  }

  if (findings.length > 0) {
    console.log("");
    console.log(`${findings.length} skill(s) failed anatomy validation`);
  } else {
    console.log("all skills conform to the anatomy");
  }
}

function repoRootForSkillsDir(skillsDir) {
  return resolve(skillsDir, "../../..");
}

function walkFiles(root) {
  const files = [];
  if (!existsSync(root)) return files;
  for (const name of readdirSync(root).sort()) {
    const path = join(root, name);
    const stat = statSync(path);
    if (stat.isDirectory()) files.push(...walkFiles(path));
    else if (stat.isFile()) files.push(path);
  }
  return files;
}

function sameBytes(left, right) {
  return readFileSync(left).equals(readFileSync(right));
}

// Every generated mirror, checked against the same canonical source. Reads the
// list from the generator so a new destination cannot be added there and silently
// escape validation.
export function validatePluginDrift(skillsDir) {
  const root = repoRootForSkillsDir(skillsDir);
  let drift = 0;
  for (const dest of MIRROR_DESTS) {
    drift += validateMirrorDrift(skillsDir, resolve(root, dest), dest);
  }
  return drift;
}

function validateMirrorDrift(skillsDir, pluginDir, label) {
  if (!existsSync(pluginDir) || !statSync(pluginDir).isDirectory()) return 0;

  let drift = 0;
  const skillDirs = readdirSync(skillsDir)
    .sort()
    .map((name) => join(skillsDir, name))
    .filter((path) => statSync(path).isDirectory());

  for (const skillDir of skillDirs) {
    const mirror = join(pluginDir, skillDir.split(/[\\/]/).at(-1));
    if (!existsSync(mirror) || !statSync(mirror).isDirectory()) {
      console.log(`${label} drift: ${mirror} missing -- run scripts/generate-plugin-symlinks.mjs`);
      drift += 1;
      continue;
    }

    for (const sourceFile of walkFiles(skillDir)) {
      const rel = relative(skillDir, sourceFile);
      const mirrorFile = join(mirror, rel);
      if (!existsSync(mirrorFile) || !statSync(mirrorFile).isFile()) {
        console.log(`${label} drift: ${mirrorFile} missing`);
        drift += 1;
        continue;
      }
      if (!sameBytes(sourceFile, mirrorFile)) {
        console.log(`${label} drift: ${mirrorFile} differs from ${sourceFile}`);
        drift += 1;
      }
    }

    for (const mirrorFile of walkFiles(mirror)) {
      const rel = relative(mirror, mirrorFile);
      const sourceFile = join(skillDir, rel);
      if (!existsSync(sourceFile) || !statSync(sourceFile).isFile()) {
        console.log(`${label} drift: ${mirrorFile} has no canonical source`);
        drift += 1;
      }
    }
  }

  for (const name of readdirSync(pluginDir).sort()) {
    const mirror = join(pluginDir, name);
    if (statSync(mirror).isDirectory() && !existsSync(join(skillsDir, name))) {
      console.log(`${label} drift: ${mirror} has no canonical skill`);
      drift += 1;
    }
  }

  if (drift === 0) console.log(`${label} mirror in sync with source`);
  else {
    console.log("");
    console.log(`${drift} ${label} mirror difference(s) found`);
  }
  return drift;
}

function readJsonObject(path) {
  if (!existsSync(path) || !statSync(path).isFile()) return [null, `missing ${path}`];
  try {
    const data = JSON.parse(readFileSync(path, "utf8"));
    if (data == null || Array.isArray(data) || typeof data !== "object") {
      return [null, `${path} must contain a JSON object`];
    }
    return [data, null];
  } catch (error) {
    return [null, `${path} is not valid JSON: ${error.message.split("\n")[0]}`];
  }
}

function firstPluginEntry(marketplace) {
  if (!Array.isArray(marketplace.plugins)) return null;
  return marketplace.plugins.find((entry) => entry && typeof entry === "object" && entry.name === "consult") ?? null;
}

export function validateCodexPluginPackage(skillsDir) {
  const root = repoRootForSkillsDir(skillsDir);
  const problems = [];
  const marketplacePath = join(root, ".agents/plugins/marketplace.json");
  const manifestPath = join(root, "plugin/.codex-plugin/plugin.json");
  const claudeMarketplacePath = join(root, ".claude-plugin/marketplace.json");
  const claudeManifestPath = join(root, "plugin/.claude-plugin/plugin.json");

  const [marketplace, marketplaceProblem] = readJsonObject(marketplacePath);
  if (marketplaceProblem) problems.push(marketplaceProblem);
  else if (marketplace) {
    if (marketplace.name !== "consult") problems.push(`${marketplacePath} name must be 'consult'`);
    if (!marketplace.interface || typeof marketplace.interface !== "object") {
      problems.push(`${marketplacePath} interface must be an object`);
    } else if (marketplace.interface.displayName !== "Consult") {
      problems.push(`${marketplacePath} interface.displayName must be 'Consult'`);
    }

    const entry = firstPluginEntry(marketplace);
    if (!entry) problems.push(`${marketplacePath} must include a 'consult' plugin entry`);
    else {
      if (!entry.source || typeof entry.source !== "object") {
        problems.push(`${marketplacePath} consult.source must be an object`);
      } else {
        if (entry.source.source !== "local") problems.push(`${marketplacePath} consult.source.source must be 'local'`);
        if (entry.source.path !== "./plugin") problems.push(`${marketplacePath} consult.source.path must be './plugin'`);
      }

      if (!entry.policy || typeof entry.policy !== "object") {
        problems.push(`${marketplacePath} consult.policy must be an object`);
      } else {
        if (entry.policy.installation !== "AVAILABLE") {
          problems.push(`${marketplacePath} consult.policy.installation must be 'AVAILABLE'`);
        }
        if (entry.policy.authentication !== "ON_INSTALL") {
          problems.push(`${marketplacePath} consult.policy.authentication must be 'ON_INSTALL'`);
        }
      }

      if (entry.category !== "Coding") problems.push(`${marketplacePath} consult.category must be 'Coding'`);
    }
  }

  const [manifest, manifestProblem] = readJsonObject(manifestPath);
  if (manifestProblem) problems.push(manifestProblem);
  else if (manifest) {
    if (manifest.name !== "consult") problems.push(`${manifestPath} name must be 'consult'`);
    if (manifest.skills !== "./skills/") problems.push(`${manifestPath} skills must be './skills/'`);
    if ("hooks" in manifest) problems.push(`${manifestPath} must not declare hooks; the Consult SessionStart hook lives in plugin/hooks/hooks.json`);

    const iface = manifest.interface;
    if (!iface || typeof iface !== "object") {
      problems.push(`${manifestPath} interface must be an object`);
    } else {
      if (iface.displayName !== "Consult") {
        problems.push(`${manifestPath} interface.displayName must be 'Consult'`);
      }
      if (iface.category !== "Coding") problems.push(`${manifestPath} interface.category must be 'Coding'`);
      if (!Array.isArray(iface.capabilities) || !["Read", "Write"].every((cap) => iface.capabilities.includes(cap))) {
        problems.push(`${manifestPath} interface.capabilities must include 'Read' and 'Write'`);
      }
      if (!Array.isArray(iface.defaultPrompt) || iface.defaultPrompt.length > 3) {
        problems.push(`${manifestPath} interface.defaultPrompt must contain at most 3 prompts`);
      }
    }

    const [claudeMarketplace, claudeProblem] = readJsonObject(claudeMarketplacePath);
    if (!claudeProblem && claudeMarketplace) {
      const claudeVersion = claudeMarketplace.metadata?.version;
      if (manifest.version !== claudeVersion) {
        problems.push(`${manifestPath} version must match ${claudeMarketplacePath} metadata.version`);
      }
      const claudeEntry = firstPluginEntry(claudeMarketplace);
      if (!claudeEntry) {
        problems.push(`${claudeMarketplacePath} must include a 'consult' plugin entry`);
      } else {
        if (claudeEntry.source !== "./plugin") {
          problems.push(`${claudeMarketplacePath} consult.source must be './plugin'`);
        }
        if (claudeEntry.version !== claudeVersion) {
          problems.push(`${claudeMarketplacePath} consult.version must match metadata.version`);
        }
      }
    }

    const [claudeManifest, claudeManifestProblem] = readJsonObject(claudeManifestPath);
    const cursorManifestPath = join(root, "plugin/.cursor-plugin/plugin.json");
    const [cursorManifest, cursorManifestProblem] = readJsonObject(cursorManifestPath);
    if (!claudeManifestProblem && claudeManifest && claudeMarketplace) {
      const claudeVersion = claudeMarketplace.metadata?.version;
      if (claudeManifest.version !== claudeVersion) {
        problems.push(`${claudeManifestPath} version must match ${claudeMarketplacePath} metadata.version`);
      }
      if (manifest.version !== claudeManifest.version) {
        problems.push(`${manifestPath} version must match ${claudeManifestPath} version`);
      }
      if ("hooks" in claudeManifest) {
        problems.push(`${claudeManifestPath} must not declare hooks; the Consult SessionStart hook lives in plugin/hooks/hooks.json`);
      }
      if (!cursorManifestProblem && cursorManifest && cursorManifest.version !== claudeVersion) {
        problems.push(`${cursorManifestPath} version must match ${claudeMarketplacePath} metadata.version`);
      }
    }
  }

  if (problems.length > 0) {
    for (const problem of problems) console.log(`codex plugin: ${problem}`);
    console.log("");
    console.log(`${problems.length} codex plugin package problem(s)`);
  } else {
    console.log("codex plugin package valid");
  }
  return problems.length;
}

export function validateCursorPluginPackage(skillsDir) {
  const root = repoRootForSkillsDir(skillsDir);
  const problems = [];
  const marketplacePath = join(root, ".cursor-plugin/marketplace.json");
  const manifestPath = join(root, "plugin/.cursor-plugin/plugin.json");
  const claudeMarketplacePath = join(root, ".claude-plugin/marketplace.json");

  const [marketplace, marketplaceProblem] = readJsonObject(marketplacePath);
  if (marketplaceProblem) problems.push(marketplaceProblem);
  else if (marketplace) {
    if (marketplace.name !== "consult") problems.push(`${marketplacePath} name must be 'consult'`);
    if (!marketplace.owner || typeof marketplace.owner !== "object") {
      problems.push(`${marketplacePath} owner must be an object`);
    } else if (marketplace.owner.name !== "Dawson Design Ltd.") {
      problems.push(`${marketplacePath} owner.name must be 'Dawson Design Ltd.'`);
    }

    const claudeVersion = (() => {
      const [claudeMarketplace] = readJsonObject(claudeMarketplacePath);
      return claudeMarketplace?.metadata?.version;
    })();

    const marketplaceVersion = marketplace.metadata?.version;
    if (claudeVersion && marketplaceVersion !== claudeVersion) {
      problems.push(`${marketplacePath} metadata.version must match ${claudeMarketplacePath} metadata.version`);
    }

    const entry = firstPluginEntry(marketplace);
    if (!entry) problems.push(`${marketplacePath} must include a 'consult' plugin entry`);
    else {
      if (entry.source !== "./plugin") {
        problems.push(`${marketplacePath} consult.source must be './plugin'`);
      }
      if (claudeVersion && entry.version !== claudeVersion) {
        problems.push(`${marketplacePath} consult.version must match metadata.version`);
      }
    }
  }

  const [manifest, manifestProblem] = readJsonObject(manifestPath);
  if (manifestProblem) problems.push(manifestProblem);
  else if (manifest) {
    if (manifest.name !== "consult") problems.push(`${manifestPath} name must be 'consult'`);
    if (manifest.skills !== "./skills/") problems.push(`${manifestPath} skills must be './skills/'`);
    if ("hooks" in manifest) {
      problems.push(`${manifestPath} must not declare hooks; the Consult SessionStart hook lives in plugin/hooks/hooks.json`);
    }

    const [claudeMarketplace, claudeProblem] = readJsonObject(claudeMarketplacePath);
    if (!claudeProblem && claudeMarketplace) {
      const claudeVersion = claudeMarketplace.metadata?.version;
      if (manifest.version !== claudeVersion) {
        problems.push(`${manifestPath} version must match ${claudeMarketplacePath} metadata.version`);
      }
    }
  }

  if (problems.length > 0) {
    for (const problem of problems) console.log(`cursor plugin: ${problem}`);
    console.log("");
    console.log(`${problems.length} cursor plugin package problem(s)`);
  } else {
    console.log("cursor plugin package valid");
  }
  return problems.length;
}

export function validateAntigravityPluginPackage(skillsDir) {
  const root = repoRootForSkillsDir(skillsDir);
  const problems = [];
  const manifestPath = join(root, "plugin/plugin.json");
  const pluginSkillsPath = join(root, "plugin/skills");

  const [manifest, manifestProblem] = readJsonObject(manifestPath);
  if (manifestProblem) problems.push(manifestProblem);
  else if (manifest && manifest.name !== "consult") {
    problems.push(`${manifestPath} name must be 'consult'`);
  }

  if (!existsSync(pluginSkillsPath) || !statSync(pluginSkillsPath).isDirectory()) {
    problems.push(`${pluginSkillsPath} must exist for Google Antigravity skills`);
  }

  if (problems.length > 0) {
    for (const problem of problems) console.log(`antigravity plugin: ${problem}`);
    console.log("");
    console.log(`${problems.length} antigravity plugin package problem(s)`);
  } else {
    console.log("antigravity plugin package valid");
  }
  return problems.length;
}

// Claude Code and Codex both discover plugin/hooks/hooks.json by convention.
// Consult ships exactly one hook there: a SessionStart command that prints the
// routing line. Anything more would turn the pack into a host enforcement layer.
function sessionStartHookProblem(hooksFile) {
  const onlyOne = "Consult ships exactly one SessionStart command hook";
  const keys = Object.keys(hooksFile);
  if (keys.length !== 1 || keys[0] !== "hooks") return `must contain only a 'hooks' key; ${onlyOne}`;
  const events = hooksFile.hooks;
  if (!events || typeof events !== "object" || Array.isArray(events)) return "hooks must be an object";
  const names = Object.keys(events);
  if (names.length !== 1 || names[0] !== "SessionStart") {
    return `declares ${names.join(", ") || "no events"}; ${onlyOne}`;
  }
  const entries = events.SessionStart;
  const handlers = Array.isArray(entries) && entries.length === 1 ? entries[0]?.hooks : null;
  if (!Array.isArray(handlers) || handlers.length !== 1) return `SessionStart must hold one handler; ${onlyOne}`;
  const [handler] = handlers;
  if (handler?.type !== "command" || typeof handler.command !== "string" || !handler.command.trim()) {
    return "SessionStart handler must be { type: 'command', command: <non-empty string> }";
  }
  return null;
}

export function validatePluginHooks(skillsDir) {
  const hooksPath = join(repoRootForSkillsDir(skillsDir), "plugin/hooks/hooks.json");
  const [hooksFile, readProblem] = readJsonObject(hooksPath);
  const shapeProblem = hooksFile ? sessionStartHookProblem(hooksFile) : null;
  const problems = [readProblem, shapeProblem && `${hooksPath} ${shapeProblem}`].filter(Boolean);

  if (problems.length > 0) {
    for (const problem of problems) console.log(`plugin hooks: ${problem}`);
    console.log("");
    console.log(`${problems.length} plugin hook problem(s)`);
  } else {
    console.log("plugin hooks valid");
  }
  return problems.length;
}

const RULE_STATUSES = new Set(["check", "judge-only", "untested"]);

function skillRuleIds(skillsDir) {
  return readdirSync(skillsDir)
    .filter((name) => existsSync(join(skillsDir, name, "SKILL.md")))
    .sort()
    .flatMap((name) => ruleNumbers(readFileSync(join(skillsDir, name, "SKILL.md"), "utf8")).map((n) => `${name}.${n}`));
}

// Every rule of every skill must appear in rules.json with a status, no entry may
// name a rule that no longer exists (a renumbered skill), and every "check" entry
// must have a function in consult_rules.py's CHECKS table.
export function ruleCoverageProblems(skillsDir, coverage, checksSource) {
  const expected = skillRuleIds(skillsDir);
  const known = new Set(expected);
  const missing = expected.filter((id) => !(id in coverage)).map((id) => `rule ${id} has no entry in rules.json`);
  const stale = Object.keys(coverage)
    .filter((id) => !known.has(id))
    .map((id) => `rules.json names ${id}, which is not a rule in its SKILL.md`);
  const invalid = Object.entries(coverage)
    .filter(([, status]) => !RULE_STATUSES.has(status))
    .map(([id, status]) => `rules.json ${id} has unknown status ${JSON.stringify(status)}`);
  const unchecked = Object.entries(coverage)
    .filter(([id, status]) => status === "check" && !checksSource.includes(`"${id}":`))
    .map(([id]) => `rules.json marks ${id} as check but consult_rules.py has no CHECKS entry for it`);
  return [...missing, ...stale, ...invalid, ...unchecked];
}

export function validateRuleCoverage(skillsDir) {
  const verifier = join(repoRootForSkillsDir(skillsDir), "eval/verifier");
  const checksPath = join(verifier, "shared/consult_rules.py");
  const [coverage, readProblem] = readJsonObject(join(verifier, "rules.json"));
  const checksProblem = existsSync(checksPath) ? null : `missing ${checksPath}`;
  const problems =
    readProblem || checksProblem
      ? [readProblem, checksProblem].filter(Boolean)
      : ruleCoverageProblems(skillsDir, coverage, readFileSync(checksPath, "utf8"));

  if (problems.length > 0) {
    for (const problem of problems) console.log(`rule coverage: ${problem}`);
    console.log("");
    console.log(`${problems.length} rule coverage problem(s)`);
  } else {
    const counts = Object.values(coverage).reduce((acc, s) => ({ ...acc, [s]: (acc[s] ?? 0) + 1 }), {});
    console.log(`rule coverage complete (${Object.entries(counts).map(([s, n]) => `${n} ${s}`).join(", ")})`);
  }
  return problems.length;
}

function writeFixture(path, text) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text, { encoding: "utf8", flag: "w" });
}

export function runSelfTest() {
  const tmp = mkdtempSync(join(tmpdir(), "has-skill-validator-"));
  try {
    cpSync(resolve(scriptDir(), "../agents/.agents/skills/workflow"), join(tmp, "good"), { recursive: true });
    writeFixture(
      join(tmp, "bad/SKILL.md"),
      `---
name: bad
description: >-
  This description is intentionally much too long for the skill routing surface
  because Codex and other agents load all skill descriptions before deciding
  which full skill body to request, so verbose trigger prose creates avoidable
  context pressure.
---

# Bad

Per Rich Hickey, prefer values over places.

An approving design or RFC is not this approval — the shapes drift here.

## Overview

Stuff.

## Common Rationalizations
| Excuse | Reality |
|---|---|
| "Should work" | It might not. |

## Red Flags
- "Probably fine"

## Tripwires
- Bullet tripwires are no longer allowed.
`,
    );
    writeFixture(
      join(tmp, "bad/references/notes.md"),
      "A reference — with an em dash.\n",
    );
    writeFixture(
      join(tmp, "workflow/SKILL.md"),
      `---
name: workflow
description: Router fixture for the routing cross-check.
---

# Workflow

## When to Use

- always

## When NOT to Use

- never

## Rules

1. check

## Workflow

   | Skill | Load when |
   | --- | --- |
   | \`good\` | always |
   | \`ghost-skill\` | never |
`,
    );
    writeFixture(
      join(tmp, "orphan/SKILL.md"),
      `---
name: orphan
description: Skill missing from the router fixture.
---

# Orphan

## When to Use

- trigger

## When NOT to Use

- other

## Rules

1. check
`,
    );

    // A quoted description containing a colon must be measured in full. Reading
    // only up to the first inner colon silently under-counts both length budgets.
    const quotedDescription =
      "Use for design-partner mode: discovery, tradeoffs, decisions, and the agreed design artifacts that later implementation work binds itself to.";
    writeFixture(
      join(tmp, "quoted/SKILL.md"),
      `---
name: quoted
description: "${quotedDescription}"
---

# Quoted

## When to Use
- trigger

## When NOT to Use
- other

## Rules
1. check
`,
    );

    writeFixture(
      join(tmp, "stale/SKILL.md"),
      `---
name: stale
description: Skill that migrated to Rules but kept a Verification mirror.
---

# Stale

## When to Use
- trigger

## When NOT to Use
- other

## Rules
1. rule

## Verification
- [ ] the same rule again

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
${Array.from({ length: MAX_TRIPWIRE_ROWS + 1 }, (_, i) => `| "Shortcut ${i}" | Do the thing. | None. |`).join("\n")}

${Array.from({ length: MAX_BODY_WORDS }, () => "word").join(" ")}
`,
    );

    const longDescription = "x".repeat(100);
    // Enough fixtures to exceed MAX_TOTAL_DESCRIPTION_LENGTH with margin, so the
    // budget assertion below does not quietly stop testing anything when the
    // ceiling is raised.
    for (let index = 0; index < Math.ceil(MAX_TOTAL_DESCRIPTION_LENGTH / 100) + 4; index += 1) {
      writeFixture(
        join(tmp, `budget-${index}/SKILL.md`),
        `---
name: budget-${index}
description: ${longDescription}
---

# Budget ${index}

## When to Use
- trigger

## When NOT to Use
- other

## Rules
1. check
`,
      );
    }

    const findings = validateSkills(tmp);
    const rendered = [
      ...findings.map((finding) => relative(tmp, finding.path)),
      ...findings.flatMap((finding) => finding.problems),
    ].join("\n");
    for (const expected of [
      "bad/SKILL.md",
      "When to Use",
      "missing section: ## Rules",
      "description too long",
      "stale/SKILL.md",
      "obsolete section: ## Verification",
      `Tripwires has ${MAX_TRIPWIRE_ROWS + 1} rows`,
      "body too long",
      "per <expert>",
      "Common Rationalizations",
      "Red Flags",
      "obsolete table header",
      "Tripwires must use the '| Trigger | Do this instead | False alarm |' table format",
      "em dash found",
      "bad/references/notes.md",
      "canonical sentence",
      "routing table names 'ghost-skill' but no such skill exists",
      "skill 'orphan' is not referenced by the workflow router",
      "description total too long",
      `quoted/SKILL.md`,
      `description too long (${quotedDescription.length} > ${MAX_DESCRIPTION_LENGTH} characters)`,
    ]) {
      if (!rendered.includes(expected)) {
        console.error(`self-test failed: missing ${JSON.stringify(expected)} in output`);
        console.error(rendered);
        return 1;
      }
    }

    if (findings.some((finding) => relative(tmp, finding.path) === "good/SKILL.md")) {
      console.error("self-test failed: good skill flagged");
      console.error(rendered);
      return 1;
    }

    if (ruleCoverageSelfTest(join(tmp, "coverage")) !== 0) return 1;

    console.log("self-test ok");
    return 0;
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

function ruleCoverageSelfTest(dir) {
  writeFixture(
    join(dir, "demo/SKILL.md"),
    "---\nname: demo\n---\n\n## Rules\n\n1. One.\n   Continued.\n2. Two.\n\n### Detail\n\n3. Not a rule.\n\n## Handoffs\n",
  );
  const problems = ruleCoverageProblems(
    dir,
    { "demo.1": "check", "demo.3": "untested", "demo.9": "maybe" },
    'CHECKS = {"other.1": x}',
  ).join("\n");
  for (const expected of [
    "rule demo.2 has no entry in rules.json",
    "rules.json names demo.3, which is not a rule",
    'rules.json demo.9 has unknown status "maybe"',
    "rules.json marks demo.1 as check but consult_rules.py has no CHECKS entry",
  ]) {
    if (!problems.includes(expected)) {
      console.error(`self-test failed: missing ${JSON.stringify(expected)} in rule coverage output`);
      console.error(problems);
      return 1;
    }
  }
  const clean = ruleCoverageProblems(dir, { "demo.1": "check", "demo.2": "judge-only" }, 'CHECKS = {"demo.1": f}');
  if (clean.length > 0) {
    console.error(`self-test failed: complete rule coverage flagged: ${clean.join("; ")}`);
    return 1;
  }
  return 0;
}

export function main(argv = process.argv.slice(2)) {
  if (argv.includes("-h") || argv.includes("--help")) {
    console.log(`Usage: node scripts/validate-skill-anatomy.mjs [skills_dir] [--self-test]

Validate SKILL.md frontmatter, required sections, and plugin drift.`);
    return 0;
  }
  if (argv.includes("--self-test")) return runSelfTest();

  const skillsDir = resolve(argv.find((arg) => !arg.startsWith("-")) ?? defaultSkillsDir());
  if (!existsSync(skillsDir) || !statSync(skillsDir).isDirectory()) {
    console.error(`not a directory: ${skillsDir}`);
    return 2;
  }

  const findings = validateSkills(skillsDir);
  printSkillFindings(skillsDir, findings);
  const drift = validatePluginDrift(skillsDir);
  const codexPluginProblems = validateCodexPluginPackage(skillsDir);
  const cursorPluginProblems = validateCursorPluginPackage(skillsDir);
  const antigravityPluginProblems = validateAntigravityPluginPackage(skillsDir);
  const pluginHookProblems = validatePluginHooks(skillsDir);
  const ruleCoverageProblemCount = validateRuleCoverage(skillsDir);
  return findings.length ||
    drift ||
    codexPluginProblems ||
    cursorPluginProblems ||
    antigravityPluginProblems ||
    pluginHookProblems ||
    ruleCoverageProblemCount
    ? 1
    : 0;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = main();
}
