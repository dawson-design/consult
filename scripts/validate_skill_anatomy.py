#!/usr/bin/env python3
"""Validate Consult skill files, the plugin mirror, plugin packages, and rule coverage.

Checks every SKILL.md against the playbook anatomy, the generated
plugin/skills mirror and plugin/hooks/hooks.json against their sources (read
from generate_plugin_symlinks.py), the Codex, Cursor, and Google Antigravity
plugin packages, and eval/verifier/rules.json coverage. Stdlib only, so it
runs with a bare python3.

It replaced a JavaScript validator and keeps that validator's findings,
messages, and exit codes, so a few helpers reproduce JavaScript semantics: lengths in
UTF-16 code units, trim()'s whitespace set, ASCII-only \\b and \\d, strict
equality, and JSON values where a missing field differs from null and an
empty object counts as present. Three JavaScript behaviors are not
reproduced. Integer-like JSON keys print in file order rather than first, and
integers beyond 2**53 print exactly, which change only wording. Regex \\s
follows Python's whitespace set, which differs from JavaScript's only for
U+001C to U+001F, U+0085, and U+FEFF inside Markdown text.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from generate_plugin_symlinks import (
    CORE_COPY,
    HOOK_DEST,
    HOOK_SOURCE,
    MIRROR_DESTS,
    hook_source_problem,
    js_length,
    js_trim,
    render_session_start_hooks,
)

REQUIRED_SECTIONS = ["When to Use", "When NOT to Use", "Rules"]
# Retired by the Rules-section anatomy. A skill that still carries one of
# these restates its rules; the validator rejects it.
OBSOLETE_RULE_SECTIONS = ["Core Ideas", "Verification", "Before Saying Done"]
# A SKILL.md is steering context, not a book. The budget is the regression
# guard for the knowledge-vs-policy trim: rules the model cannot derive fit
# in this space; explanations of standard practice do not.
MAX_BODY_WORDS = 700
# Raised budgets, each with a reason. workflow carries the validator-mandated
# 24-row routing table (~215 words) plus the sign-off table. workflow,
# code-review, and proof also absorbed the 12.1.0 host-harness and 13.1.0
# fresh-context-review policy, which is rule text, not explanation. workflow
# rose to 1,120 for the plan-handoff rule, which lets a cheaper model build
# from a plan a stronger model wrote, and to 1,135 for the issue-tracking
# routing row the router cross-check requires, and to 1,356 for the build-stage
# rule: build data, then contracts, then transformations, with a sign-off
# gate before each gated stage. No neighbouring skill can own the order,
# because only workflow loads on every task. workflow rose to 1,501 for the
# code-shape rule (function length, nesting depth, named compound
# conditions, composition over inheritance), moved from architecture
# because it applies to every function an agent writes and architecture
# loads only for boundary work, and to 1,518 when the sign-off rule (Rule 7)
# replaced "durable shapes" with a plain statement of what needs sign-off
# and why. It fell to 1,340 when plan-file detail, stage delegation, and
# per-stage review scope moved to workflow references and Rule 7 shrank to
# the gate, its list, and the no-human path
# (AGENTS.md: workflow holds only guidance for all code plus routing),
# then to 1,181 when duplicated statements across the Rules and Workflow
# steps were merged or cut, the Rules stopped naming skills before the
# routing table introduces them, the skill-conflict rule was deleted, and
# Rule 7 dropped its no-human path.
# It rose to 1,201 for Rule 8's delegated-model sentence, after trimming
# restated Workflow steps 3 and 5 paid for part of it, then fell to 947 when
# the rules every code change needs (the Iron Law and old Rules 1-5 and 10)
# moved to the always-on core, now agents/.agents/core.md.
# It fell to 942 when step 1's compatibility-shim clause became core rule 7.
# It rose to 943 when the git-workflow routing row gained "worktrees", then
# fell to 928 when workflow's pointer to the core was shortened.
# proof rose to 1,050 for the
# test-level and test-oracle rules: expected outputs come from the
# spec, and agents never edit an existing test to make a change pass. api
# rose to 730 so Rules 1 and 2 state its REST compatibility policy (which
# changes need approval, who counts as an independent consumer, and what
# needs a successor) in plain sentences instead of dense ones.
BODY_WORD_EXCEPTIONS = {"workflow": 928, "proof": 1050, "code-review": 950, "api": 730}
MAX_TRIPWIRE_ROWS = 8
MAX_DESCRIPTION_LENGTH = 120
# ~600 tokens of routing surface that every host loads before picking a skill.
# Chosen deliberately once the measurement was honest: the previous 2,000 was
# never enforced (descriptions were truncated at their first inner colon), and
# the pack turned out to be at 2,069 the whole time. 2,400 left room for about
# four more skills. issue-tracking brought the pack to 2,399, so the next skill
# needs keyword cuts elsewhere or a stated reason to raise this.
MAX_TOTAL_DESCRIPTION_LENGTH = 2400

NAME_RE = re.compile(r"^name:\s+[a-z][a-z0-9-]*\s*$", re.MULTILINE)
# A skill that names a model switches the host's model when it loads, which
# throws away the prompt cache and re-reads the whole session uncached.
MODEL_KEY_RE = re.compile(r"^model:", re.MULTILINE)
# The lookarounds are JavaScript's ASCII-only \b.
ATTRIBUTION_RE = re.compile(r"(?<![A-Za-z0-9_])[Pp]er\s+(?:[A-Z][a-z]+\s+)?[A-Z][a-z]+(?![A-Za-z0-9_])")
EM_DASH = "—"
EM_DASH_PROBLEM = "em dash found -- use a period, colon, comma, or parentheses instead"
# One authoritative phrasing of the direction-vs-shapes approval rule. Skills
# that invoke the concept must carry this sentence verbatim so the semantics
# cannot drift file by file.
APPROVAL_CONCEPT_RE = re.compile(r"approving design or RFC", re.IGNORECASE)
CANONICAL_APPROVAL_SENTENCE = "An approving design or RFC approves the direction, not the concrete shapes"
TRIPWIRES_TABLE_HEADER_RE = re.compile(r"^\|\s*Trigger\s*\|\s*Do this instead\s*\|\s*False alarm\s*\|", re.MULTILINE)
TRIPWIRES_FORMAT_PROBLEM = "Tripwires must use the '| Trigger | Do this instead | False alarm |' table format"
NO_MANIFEST_HOOKS = "must not declare hooks; the Consult SessionStart hook lives in plugin/hooks/hooks.json"
GENERATOR_COMMAND = "python3 scripts/generate_plugin_symlinks.py"
RULE_STATUSES = {"check", "judge-only", "untested"}
# The Consult core (HOOK_SOURCE, the SessionStart hook's source) numbers its
# rules under `## Rules` like a SKILL.md, and its eval ids are `core.<n>`.

USAGE = """Usage: python3 scripts/validate_skill_anatomy.py [skills_dir] [--self-test]

Validate SKILL.md frontmatter, required sections, and plugin drift."""


class Finding(NamedTuple):
    """The problems found in one file. `path` is absolute; `problems` is never empty."""

    path: str
    problems: list[str]


# JavaScript value semantics for parsed JSON.

# What a JavaScript property read returns for an absent field: unlike None
# (JSON null), it equals only itself.
MISSING = object()


def field(value: Any, key: str) -> Any:
    """Read `value[key]` as JavaScript's `value?.[key]` would: MISSING unless `value` is an object holding it."""
    if isinstance(value, dict) and key in value:
        return value[key]
    return MISSING


def is_object(value: Any) -> bool:
    """Say whether JavaScript's `value && typeof value === "object"` holds (arrays included)."""
    return isinstance(value, (dict, list))


def js_strict_equal(left: Any, right: Any) -> bool:
    """Say whether JavaScript's `left === right` holds for two separately parsed JSON values.

    Objects and arrays from different places are never identical, and a
    boolean never equals a number.
    """
    if is_object(left) or is_object(right):
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def js_truthy(value: Any) -> bool:
    """Say whether JavaScript treats `value` as true: empty objects and arrays are true."""
    if value is MISSING or value is None:
        return False
    return is_object(value) or bool(value)


def js_json(value: Any) -> str:
    """Return JSON.stringify(value) for a parsed JSON value."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def read_text(path: str) -> str:
    """Read `path` as UTF-8, replacing invalid bytes as Node's readFileSync does."""
    return Path(path).read_text(encoding="utf8", errors="replace")


def lines_of(text: str) -> list[str]:
    """Split `text` into lines on LF or CRLF."""
    return re.split(r"\r?\n", text)


def head_of(body: str) -> str:
    """Return the first 30 lines of `body`, where the frontmatter lives."""
    return "\n".join(lines_of(body)[:30])


def first_index(lines: list[str], pattern: str) -> int | None:
    """Return the index of the first line that `pattern` matches at its start, or None."""
    return next((i for i, line in enumerate(lines) if re.match(pattern, line)), None)


# Reading a SKILL.md.


def section_re(name: str) -> re.Pattern[str]:
    """Return a pattern matching a `##` (or deeper) heading named exactly `name`."""
    return re.compile(rf"^##+\s+{re.escape(name)}\s*$", re.MULTILINE)


def tripwire_row_count(body: str) -> int:
    """Count the quoted-trigger rows in the `## Tripwires` table."""
    lines = lines_of(body)
    start = first_index(lines, r"##\s+Tripwires\s*$")
    if start is None:
        return 0
    rows = 0
    for line in lines[start + 1 :]:
        if re.match(r"##\s+", line):
            break
        if re.match(r'\|\s*"', line):
            rows += 1
    return rows


def rule_numbers(body: str) -> list[int]:
    """Return the numbers of the top-level rules in `## Rules`, up to the first `##` or `###`.

    Rule ids (`<skill>.<n>`) key the eval's rule checks in eval/verifier/rules.json.
    """
    lines = lines_of(body)
    start = first_index(lines, r"##\s+Rules\s*$")
    if start is None:
        return []
    rest = lines[start + 1 :]
    end = first_index(rest, r"###?\s+")
    section = rest if end is None else rest[:end]
    matches = (re.match(r"([0-9]+)\.\s", line) for line in section)
    return [int(match[1]) for match in matches if match]


def body_word_count(body: str) -> int:
    """Count words after the frontmatter: tokens holding a letter or digit, so table pipes are free."""
    without_frontmatter = re.sub(r"^---[\s\S]*?\n---\n", "", body, count=1)
    tokens = re.split(r"\s+", without_frontmatter)
    return sum(1 for token in tokens if any(ch.isalpha() or ch.isnumeric() for ch in token))


def skill_name(head: str) -> str:
    """Return the frontmatter `name:` value, or "" when there is none."""
    match = re.search(r"^name:\s+(\S+)", head, re.MULTILINE)
    return match[1] if match else ""


def body_without_reference_sections(body: str) -> str:
    """Return `body` with everything from the first References or Canon heading removed."""
    kept = []
    for line in lines_of(body):
        if re.match(r"##+ (References|Canon)\s*$", line):
            break
        kept.append(line)
    return "\n".join(kept)


def frontmatter_description(head: str) -> str | None:
    """Return the frontmatter description, joining folded lines, or None when there is none."""
    description = []
    in_description = False
    for line in lines_of(head):
        if line.startswith("description:"):
            in_description = True
            value = js_trim(line[len("description:") :])
            if value and value not in {">", ">-", "|", "|-"}:
                description.append(value)
            continue
        if not in_description:
            continue
        if not line.startswith("  "):
            break
        description.append(js_trim(line))
    if not in_description:
        return None
    return unquote_scalar(" ".join(description))


def unquote_scalar(value: str) -> str:
    """Strip a quoted YAML scalar's delimiters, so the budgets measure what an agent reads."""
    for quote in ['"', "'"]:
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


# Checking a SKILL.md.


def frontmatter_problems(body: str, head: str) -> list[str]:
    """Check the frontmatter: kebab-case name, no model key, a description within budget."""
    problems = []
    if not NAME_RE.search(head):
        problems.append("frontmatter missing name or not kebab-case")
    frontmatter = re.match(r"---\r?\n([\s\S]*?)\r?\n---", body)
    if MODEL_KEY_RE.search(frontmatter[1] if frontmatter else ""):
        problems.append("frontmatter sets model -- a skill-level model switch discards the host's prompt cache")
    description = frontmatter_description(head)
    if description is None:
        problems.append("frontmatter missing description")
    elif js_length(description) > MAX_DESCRIPTION_LENGTH:
        length = js_length(description)
        problems.append(f"frontmatter description too long ({length} > {MAX_DESCRIPTION_LENGTH} characters)")
    return problems


def section_problems(body: str, head: str) -> list[str]:
    """Check required and obsolete sections, and the body word budget."""
    problems = [f"missing section: ## {name}" for name in REQUIRED_SECTIONS if not section_re(name).search(body)]
    for name in OBSOLETE_RULE_SECTIONS:
        if section_re(name).search(body):
            problems.append(f"obsolete section: ## {name} -- state the rule once under ## Rules")
    words = body_word_count(body)
    budget = BODY_WORD_EXCEPTIONS.get(skill_name(head), MAX_BODY_WORDS)
    if words > budget:
        problems.append(f"body too long ({words} > {budget} words) -- keep policy, drop explanation")
    return problems


def tripwire_problems(body: str) -> list[str]:
    """Check for retired rationalization sections and the Tripwires table's format and size."""
    problems = []
    if section_re("Common Rationalizations").search(body):
        problems.append("obsolete section: ## Common Rationalizations -- use ## Tripwires")
    if section_re("Red Flags").search(body):
        problems.append("obsolete section: ## Red Flags -- fold into ## Tripwires")
    if re.search(r"^\|\s*Excuse\s*\|\s*Reality\s*\|", body, re.MULTILINE):
        problems.append("obsolete table header: use the '| Trigger | Do this instead | False alarm |' Tripwires table")
    if section_re("Tripwires").search(body) and not TRIPWIRES_TABLE_HEADER_RE.search(body):
        problems.append(TRIPWIRES_FORMAT_PROBLEM)
    rows = tripwire_row_count(body)
    if rows > MAX_TRIPWIRE_ROWS:
        problems.append(
            f"Tripwires has {rows} rows (max {MAX_TRIPWIRE_ROWS}) -- keep only high-probability failure moments"
        )
    return problems


def prose_problems(body: str) -> list[str]:
    """Check for em dashes, a drifted approval sentence, and inline attribution."""
    problems = []
    if EM_DASH in body:
        problems.append(EM_DASH_PROBLEM)
    flattened = re.sub(r"\s+", " ", body)
    if APPROVAL_CONCEPT_RE.search(flattened) and CANONICAL_APPROVAL_SENTENCE not in flattened:
        problems.append(
            f"'approving design or RFC' used without the canonical sentence: \"{CANONICAL_APPROVAL_SENTENCE}\""
        )
    attribution_lines = [
        line
        for line in lines_of(body_without_reference_sections(body))
        if not line.startswith(">") and ATTRIBUTION_RE.search(line)
    ]
    if attribution_lines:
        problems.append("inline 'per <expert>' attribution found -- move to References")
    return problems


def validate_skill_file(path: str) -> Finding | None:
    """Check one SKILL.md against the anatomy; return its problems, or None when it conforms."""
    body = read_text(path)
    head = head_of(body)
    problems = [
        *frontmatter_problems(body, head),
        *section_problems(body, head),
        *tripwire_problems(body),
        *prose_problems(body),
    ]
    return Finding(path, problems) if problems else None


def walk_files(root: str) -> list[str]:
    """Return every file under `root`, depth first in sorted order; [] when `root` is absent."""
    if not os.path.exists(root):
        return []
    files = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            files.extend(walk_files(path))
        elif os.path.isfile(path):
            files.append(path)
    return files


def validate_skill_references(skill_dir: str) -> list[Finding]:
    """Report each Markdown file under the skill's references/ that holds an em dash."""
    paths = walk_files(os.path.join(skill_dir, "references"))
    return [Finding(path, [EM_DASH_PROBLEM]) for path in paths if path.endswith(".md") and EM_DASH in read_text(path)]


def skill_names(skills_dir: str) -> list[str]:
    """Return the sorted names of the directories in `skills_dir` that hold a SKILL.md."""
    names = sorted(os.listdir(skills_dir))
    return [name for name in names if os.path.exists(os.path.join(skills_dir, name, "SKILL.md"))]


def validate_workflow_routing(skills_dir: str) -> list[Finding]:
    """Cross-check the workflow skill's routing tables against the skill set, in both directions.

    Every backticked name in a workflow table row must be a real skill, and
    every skill must be named somewhere in the workflow body.
    """
    workflow_file = os.path.join(skills_dir, "workflow", "SKILL.md")
    if not os.path.exists(workflow_file):
        return []
    body = read_text(workflow_file)
    names = skill_names(skills_dir)
    routed = re.findall(r"^\s*\|\s*`([a-z][a-z0-9-]*)`\s*\|", body, re.MULTILINE)
    problems = [f"routing table names '{name}' but no such skill exists" for name in routed if name not in names]
    for name in names:
        if name != "workflow" and f"`{name}`" not in body:
            problems.append(f"skill '{name}' is not referenced by the workflow router")
    return [Finding(workflow_file, problems)] if problems else []


def validate_skills(skills_dir: str) -> list[Finding]:
    """Check every skill, its references, the workflow router, and the pack-wide description budget."""
    findings = []
    total_description_length = 0
    for name in sorted(os.listdir(skills_dir)):
        skill_file = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.exists(skill_file):
            continue
        description = frontmatter_description(head_of(read_text(skill_file)))
        if description is not None:
            total_description_length += js_length(description)
        finding = validate_skill_file(skill_file)
        if finding:
            findings.append(finding)
        findings.extend(validate_skill_references(os.path.join(skills_dir, name)))
    findings.extend(validate_workflow_routing(skills_dir))
    if total_description_length > MAX_TOTAL_DESCRIPTION_LENGTH:
        total = f"{total_description_length} > {MAX_TOTAL_DESCRIPTION_LENGTH} characters"
        problem = f"frontmatter description total too long ({total})"
        findings.append(Finding(os.path.join(skills_dir, "SKILL_DESCRIPTIONS"), [problem]))
    return findings


def print_skill_findings(skills_dir: str, findings: list[Finding]) -> None:
    """Print each finding under its path relative to `skills_dir`, then a summary line."""
    for finding in findings:
        print(os.path.relpath(finding.path, skills_dir))
        for problem in finding.problems:
            print(f"  - {problem}")
    if findings:
        print()
        print(f"{len(findings)} skill(s) failed anatomy validation")
    else:
        print("all skills conform to the anatomy")


# Mirror drift.


def repo_root_for_skills_dir(skills_dir: str) -> str:
    """Return the repo root for a skills dir at <root>/agents/.agents/skills."""
    return os.path.abspath(os.path.join(skills_dir, "../../.."))


def same_bytes(left: str, right: str) -> bool:
    """Say whether two files hold the same bytes."""
    return Path(left).read_bytes() == Path(right).read_bytes()


def validate_plugin_drift(skills_dir: str) -> int:
    """Check every generated mirror against the canonical skills; return the difference count.

    Reads the list from the generator, so a new destination cannot be added
    there and silently escape validation.
    """
    root = repo_root_for_skills_dir(skills_dir)
    return sum(validate_mirror_drift(skills_dir, os.path.join(root, dest), dest) for dest in MIRROR_DESTS)


def skill_mirror_drift(skill_dir: str, mirror: str, label: str) -> int:
    """Print and count the differences between one canonical skill and its mirror copy."""
    if not os.path.isdir(mirror):
        print(f"{label} drift: {mirror} missing -- run {GENERATOR_COMMAND}")
        return 1
    drift = 0
    for source_file in walk_files(skill_dir):
        mirror_file = os.path.join(mirror, os.path.relpath(source_file, skill_dir))
        if not os.path.isfile(mirror_file):
            print(f"{label} drift: {mirror_file} missing")
            drift += 1
        elif not same_bytes(source_file, mirror_file):
            print(f"{label} drift: {mirror_file} differs from {source_file}")
            drift += 1
    for mirror_file in walk_files(mirror):
        if not os.path.isfile(os.path.join(skill_dir, os.path.relpath(mirror_file, mirror))):
            print(f"{label} drift: {mirror_file} has no canonical source")
            drift += 1
    return drift


def validate_mirror_drift(skills_dir: str, plugin_dir: str, label: str) -> int:
    """Check one mirror directory against the canonical skills; print and return the difference count."""
    if not os.path.isdir(plugin_dir):
        return 0
    skill_dirs = [os.path.join(skills_dir, name) for name in sorted(os.listdir(skills_dir))]
    drift = 0
    for skill_dir in filter(os.path.isdir, skill_dirs):
        drift += skill_mirror_drift(skill_dir, os.path.join(plugin_dir, os.path.basename(skill_dir)), label)
    for name in sorted(os.listdir(plugin_dir)):
        mirror = os.path.join(plugin_dir, name)
        if os.path.isdir(mirror) and not os.path.exists(os.path.join(skills_dir, name)):
            print(f"{label} drift: {mirror} has no canonical skill")
            drift += 1
    if drift == 0:
        print(f"{label} mirror in sync with source")
    else:
        print()
        print(f"{drift} {label} mirror difference(s) found")
    return drift


# Plugin packages.


def reject_constant(name: str) -> Any:
    """Refuse NaN and Infinity, which JSON.parse rejects and json.loads accepts."""
    raise ValueError(f"Unexpected token {name}")


def js_number(text: str) -> int | float:
    """Parse a JSON number with a fraction or exponent as JavaScript does: integral values are integers.

    JavaScript has one number type, so 1.0 equals 1 and prints as 1.
    """
    value = float(text)
    return int(value) if value.is_integer() else value


def read_json_object(path: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse `path` as a JSON object; return (object, None) or (None, problem)."""
    if not os.path.isfile(path):
        return None, f"missing {path}"
    try:
        data = json.loads(read_text(path), parse_float=js_number, parse_constant=reject_constant)
    except ValueError as error:
        return None, f"{path} is not valid JSON: {str(error).splitlines()[0]}"
    if not isinstance(data, dict):
        return None, f"{path} must contain a JSON object"
    return data, None


def first_plugin_entry(marketplace: dict[str, Any]) -> dict[str, Any] | None:
    """Return the marketplace's `consult` plugin entry, or None."""
    plugins = field(marketplace, "plugins")
    if not isinstance(plugins, list):
        return None
    return next((entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == "consult"), None)


def report(prefix: str, problems: list[str], count_label: str, ok_message: str) -> int:
    """Print each problem under `prefix` and a count, or `ok_message`; return the problem count."""
    if problems:
        for problem in problems:
            print(f"{prefix}: {problem}")
        print()
        print(f"{len(problems)} {count_label}")
    else:
        print(ok_message)
    return len(problems)


def codex_marketplace_entry_problems(path: str, entry: dict[str, Any]) -> list[str]:
    """Check the Codex marketplace's consult entry: local ./plugin source, policy, category."""
    problems = []
    source = field(entry, "source")
    if not is_object(source):
        problems.append(f"{path} consult.source must be an object")
    else:
        if field(source, "source") != "local":
            problems.append(f"{path} consult.source.source must be 'local'")
        if field(source, "path") != "./plugin":
            problems.append(f"{path} consult.source.path must be './plugin'")
    policy = field(entry, "policy")
    if not is_object(policy):
        problems.append(f"{path} consult.policy must be an object")
    else:
        if field(policy, "installation") != "AVAILABLE":
            problems.append(f"{path} consult.policy.installation must be 'AVAILABLE'")
        if field(policy, "authentication") != "ON_INSTALL":
            problems.append(f"{path} consult.policy.authentication must be 'ON_INSTALL'")
    if field(entry, "category") != "Coding":
        problems.append(f"{path} consult.category must be 'Coding'")
    return problems


def codex_marketplace_problems(path: str, marketplace: dict[str, Any]) -> list[str]:
    """Check .agents/plugins/marketplace.json: name, interface, and the consult entry."""
    problems = []
    if field(marketplace, "name") != "consult":
        problems.append(f"{path} name must be 'consult'")
    interface = field(marketplace, "interface")
    if not is_object(interface):
        problems.append(f"{path} interface must be an object")
    elif field(interface, "displayName") != "Consult":
        problems.append(f"{path} interface.displayName must be 'Consult'")
    entry = first_plugin_entry(marketplace)
    if entry is None:
        problems.append(f"{path} must include a 'consult' plugin entry")
    else:
        problems.extend(codex_marketplace_entry_problems(path, entry))
    return problems


def codex_interface_problems(path: str, iface: Any) -> list[str]:
    """Check the Codex manifest's interface block."""
    if not is_object(iface):
        return [f"{path} interface must be an object"]
    problems = []
    if field(iface, "displayName") != "Consult":
        problems.append(f"{path} interface.displayName must be 'Consult'")
    if field(iface, "category") != "Coding":
        problems.append(f"{path} interface.category must be 'Coding'")
    capabilities = field(iface, "capabilities")
    if not isinstance(capabilities, list) or not all(cap in capabilities for cap in ["Read", "Write"]):
        problems.append(f"{path} interface.capabilities must include 'Read' and 'Write'")
    prompts = field(iface, "defaultPrompt")
    if not isinstance(prompts, list) or len(prompts) > 3:
        problems.append(f"{path} interface.defaultPrompt must contain at most 3 prompts")
    return problems


def claude_marketplace_problems(manifest_path: str, manifest: dict[str, Any], path: str, marketplace: Any) -> list[str]:
    """Check the Codex manifest version and the consult entry against the Claude marketplace."""
    problems = []
    claude_version = field(field(marketplace, "metadata"), "version")
    if not js_strict_equal(field(manifest, "version"), claude_version):
        problems.append(f"{manifest_path} version must match {path} metadata.version")
    entry = first_plugin_entry(marketplace)
    if entry is None:
        problems.append(f"{path} must include a 'consult' plugin entry")
        return problems
    if field(entry, "source") != "./plugin":
        problems.append(f"{path} consult.source must be './plugin'")
    if not js_strict_equal(field(entry, "version"), claude_version):
        problems.append(f"{path} consult.version must match metadata.version")
    return problems


def manifest_version_problems(root: str, manifest_path: str, manifest: dict[str, Any], marketplace: Any) -> list[str]:
    """Check the Claude and Cursor manifests against the Claude marketplace and the Codex manifest."""
    marketplace_path = os.path.join(root, ".claude-plugin/marketplace.json")
    claude_path = os.path.join(root, "plugin/.claude-plugin/plugin.json")
    cursor_path = os.path.join(root, "plugin/.cursor-plugin/plugin.json")
    claude_manifest, _ = read_json_object(claude_path)
    cursor_manifest, _ = read_json_object(cursor_path)
    if claude_manifest is None or marketplace is None:
        return []
    problems = []
    claude_version = field(field(marketplace, "metadata"), "version")
    if not js_strict_equal(field(claude_manifest, "version"), claude_version):
        problems.append(f"{claude_path} version must match {marketplace_path} metadata.version")
    if not js_strict_equal(field(manifest, "version"), field(claude_manifest, "version")):
        problems.append(f"{manifest_path} version must match {claude_path} version")
    if "hooks" in claude_manifest:
        problems.append(f"{claude_path} {NO_MANIFEST_HOOKS}")
    if cursor_manifest is not None and not js_strict_equal(field(cursor_manifest, "version"), claude_version):
        problems.append(f"{cursor_path} version must match {marketplace_path} metadata.version")
    return problems


def codex_manifest_problems(root: str, path: str, manifest: dict[str, Any]) -> list[str]:
    """Check plugin/.codex-plugin/plugin.json, then the package versions it must agree with."""
    problems = []
    if field(manifest, "name") != "consult":
        problems.append(f"{path} name must be 'consult'")
    if field(manifest, "skills") != "./skills/":
        problems.append(f"{path} skills must be './skills/'")
    if "hooks" in manifest:
        problems.append(f"{path} {NO_MANIFEST_HOOKS}")
    problems.extend(codex_interface_problems(path, field(manifest, "interface")))
    marketplace_path = os.path.join(root, ".claude-plugin/marketplace.json")
    marketplace, _ = read_json_object(marketplace_path)
    if marketplace is not None:
        problems.extend(claude_marketplace_problems(path, manifest, marketplace_path, marketplace))
    problems.extend(manifest_version_problems(root, path, manifest, marketplace))
    return problems


def validate_codex_plugin_package(skills_dir: str) -> int:
    """Check the Codex marketplace and manifest, and package version agreement; return the problem count."""
    root = repo_root_for_skills_dir(skills_dir)
    problems = []
    marketplace_path = os.path.join(root, ".agents/plugins/marketplace.json")
    marketplace, marketplace_problem = read_json_object(marketplace_path)
    if marketplace is None:
        problems.append(marketplace_problem)
    else:
        problems.extend(codex_marketplace_problems(marketplace_path, marketplace))
    manifest_path = os.path.join(root, "plugin/.codex-plugin/plugin.json")
    manifest, manifest_problem = read_json_object(manifest_path)
    if manifest is None:
        problems.append(manifest_problem)
    else:
        problems.extend(codex_manifest_problems(root, manifest_path, manifest))
    return report("codex plugin", problems, "codex plugin package problem(s)", "codex plugin package valid")


def cursor_marketplace_problems(
    path: str, marketplace: dict[str, Any], claude_version: Any, claude_path: str
) -> list[str]:
    """Check .cursor-plugin/marketplace.json: name, owner, versions, and the consult entry."""
    problems = []
    if field(marketplace, "name") != "consult":
        problems.append(f"{path} name must be 'consult'")
    owner = field(marketplace, "owner")
    if not is_object(owner):
        problems.append(f"{path} owner must be an object")
    elif field(owner, "name") != "Dawson Design Ltd.":
        problems.append(f"{path} owner.name must be 'Dawson Design Ltd.'")
    if js_truthy(claude_version) and not js_strict_equal(
        field(field(marketplace, "metadata"), "version"), claude_version
    ):
        problems.append(f"{path} metadata.version must match {claude_path} metadata.version")
    entry = first_plugin_entry(marketplace)
    if entry is None:
        problems.append(f"{path} must include a 'consult' plugin entry")
        return problems
    if field(entry, "source") != "./plugin":
        problems.append(f"{path} consult.source must be './plugin'")
    if js_truthy(claude_version) and not js_strict_equal(field(entry, "version"), claude_version):
        problems.append(f"{path} consult.version must match metadata.version")
    return problems


def cursor_manifest_problems(
    path: str, manifest: dict[str, Any], claude_marketplace: Any, claude_path: str
) -> list[str]:
    """Check plugin/.cursor-plugin/plugin.json: name, skills path, no hooks, version."""
    problems = []
    if field(manifest, "name") != "consult":
        problems.append(f"{path} name must be 'consult'")
    if field(manifest, "skills") != "./skills/":
        problems.append(f"{path} skills must be './skills/'")
    if "hooks" in manifest:
        problems.append(f"{path} {NO_MANIFEST_HOOKS}")
    if claude_marketplace is not None:
        claude_version = field(field(claude_marketplace, "metadata"), "version")
        if not js_strict_equal(field(manifest, "version"), claude_version):
            problems.append(f"{path} version must match {claude_path} metadata.version")
    return problems


def validate_cursor_plugin_package(skills_dir: str) -> int:
    """Check the Cursor marketplace and manifest; return the problem count."""
    root = repo_root_for_skills_dir(skills_dir)
    problems = []
    claude_path = os.path.join(root, ".claude-plugin/marketplace.json")
    marketplace_path = os.path.join(root, ".cursor-plugin/marketplace.json")
    marketplace, marketplace_problem = read_json_object(marketplace_path)
    if marketplace is None:
        problems.append(marketplace_problem)
    else:
        claude_version = field(field(read_json_object(claude_path)[0], "metadata"), "version")
        problems.extend(cursor_marketplace_problems(marketplace_path, marketplace, claude_version, claude_path))
    manifest_path = os.path.join(root, "plugin/.cursor-plugin/plugin.json")
    manifest, manifest_problem = read_json_object(manifest_path)
    if manifest is None:
        problems.append(manifest_problem)
    else:
        claude_marketplace, _ = read_json_object(claude_path)
        problems.extend(cursor_manifest_problems(manifest_path, manifest, claude_marketplace, claude_path))
    return report("cursor plugin", problems, "cursor plugin package problem(s)", "cursor plugin package valid")


def validate_antigravity_plugin_package(skills_dir: str) -> int:
    """Check the Antigravity marker plugin/plugin.json and the skills it ships; return the problem count."""
    root = repo_root_for_skills_dir(skills_dir)
    problems = []
    manifest_path = os.path.join(root, "plugin/plugin.json")
    plugin_skills_path = os.path.join(root, "plugin/skills")
    manifest, manifest_problem = read_json_object(manifest_path)
    if manifest is None:
        problems.append(manifest_problem)
    elif field(manifest, "name") != "consult":
        problems.append(f"{manifest_path} name must be 'consult'")
    if not os.path.isdir(plugin_skills_path):
        problems.append(f"{plugin_skills_path} must exist for Google Antigravity skills")
    return report(
        "antigravity plugin", problems, "antigravity plugin package problem(s)", "antigravity plugin package valid"
    )


# The plugin hooks file.


def session_start_hook_problem(hooks_file: dict[str, Any]) -> str | None:
    """Say why hooks.json is not exactly one SessionStart command hook, or None.

    Claude Code and Codex both discover plugin/hooks/hooks.json by convention.
    Consult ships one hook there, which prints the Consult core; anything more
    would turn the pack into a host enforcement layer.
    """
    only_one = "Consult ships exactly one SessionStart command hook"
    if list(hooks_file) != ["hooks"]:
        return f"must contain only a 'hooks' key; {only_one}"
    events = hooks_file["hooks"]
    if not isinstance(events, dict):
        return "hooks must be an object"
    if list(events) != ["SessionStart"]:
        return f"declares {', '.join(events) or 'no events'}; {only_one}"
    entries = events["SessionStart"]
    handlers = field(entries[0], "hooks") if isinstance(entries, list) and len(entries) == 1 else None
    if not isinstance(handlers, list) or len(handlers) != 1:
        return f"SessionStart must hold one handler; {only_one}"
    command = field(handlers[0], "command")
    if field(handlers[0], "type") != "command" or not isinstance(command, str) or not js_trim(command):
        return "SessionStart handler must be { type: 'command', command: <non-empty string> }"
    return None


def session_start_hook_drift_problem(root: str, hooks_text: str) -> str | None:
    """Say how hooks.json differs from what HOOK_SOURCE generates, or None.

    CRs are ignored so a CRLF checkout does not report drift that is not there.
    """
    source_path = os.path.join(root, HOOK_SOURCE)
    if not os.path.exists(source_path):
        return f"missing {HOOK_SOURCE}, the source of {HOOK_DEST}"
    markdown = read_text(source_path)
    source_problem = hook_source_problem(markdown)
    if source_problem:
        return f"{HOOK_SOURCE} {source_problem}"
    if EM_DASH in markdown:
        return f"{HOOK_SOURCE} has an em dash -- use a period, colon, comma, or parentheses instead"
    if hooks_text.replace("\r", "") != render_session_start_hooks(markdown):
        return f"{HOOK_DEST} differs from {HOOK_SOURCE} -- run {GENERATOR_COMMAND}"
    copy_path = os.path.join(root, CORE_COPY)
    if not os.path.exists(copy_path) or not same_bytes(source_path, copy_path):
        return (
            f"{CORE_COPY} is missing or differs from {HOOK_SOURCE}; it is generated, so move any edits"
            f" to {HOOK_SOURCE}, then run {GENERATOR_COMMAND}"
        )
    return None


def validate_plugin_hooks(skills_dir: str) -> int:
    """Check plugin/hooks/hooks.json's shape and drift from core.md; return the problem count."""
    root = repo_root_for_skills_dir(skills_dir)
    hooks_path = os.path.join(root, HOOK_DEST)
    hooks_file, read_problem = read_json_object(hooks_path)
    shape_problem = session_start_hook_problem(hooks_file) if hooks_file is not None else None
    drift_problem = None
    if hooks_file is not None and not shape_problem:
        drift_problem = session_start_hook_drift_problem(root, read_text(hooks_path))
    shape = f"{hooks_path} {shape_problem}" if shape_problem else None
    problems = [problem for problem in [read_problem, shape, drift_problem] if problem]
    return report("plugin hooks", problems, "plugin hook problem(s)", "plugin hooks valid")


# Rule coverage in eval/verifier/rules.json.


def skill_rule_ids(skills_dir: str) -> list[str]:
    """Return every rule id: `<skill>.<n>` for each skill's rules, then `core.<n>` for core.md's."""
    ids = []
    for name in skill_names(skills_dir):
        ids.extend(f"{name}.{n}" for n in rule_numbers(read_text(os.path.join(skills_dir, name, "SKILL.md"))))
    core_path = os.path.join(repo_root_for_skills_dir(skills_dir), HOOK_SOURCE)
    if os.path.exists(core_path):
        ids.extend(f"core.{n}" for n in rule_numbers(read_text(core_path)))
    return ids


def rule_coverage_problems(skills_dir: str, coverage: dict[str, Any], checks_source: str) -> list[str]:
    """Compare rules.json with the rules the skills and core.md define.

    Every rule needs an entry with a known status, no entry may name a rule
    that no longer exists (a renumbered skill), and every "check" entry needs
    a function in consult_rules.py's CHECKS table.
    """
    expected = skill_rule_ids(skills_dir)
    known = set(expected)
    missing = [f"rule {rule} has no entry in rules.json" for rule in expected if rule not in coverage]
    stale = [
        f"rules.json names {rule}, which is not a rule in its SKILL.md or core.md"
        for rule in coverage
        if rule not in known
    ]
    invalid = [
        f"rules.json {rule} has unknown status {js_json(status)}"
        for rule, status in coverage.items()
        if not (isinstance(status, str) and status in RULE_STATUSES)
    ]
    unchecked = [
        f"rules.json marks {rule} as check but consult_rules.py has no CHECKS entry for it"
        for rule, status in coverage.items()
        if status == "check" and f'"{rule}":' not in checks_source
    ]
    return [*missing, *stale, *invalid, *unchecked]


def coverage_summary(coverage: dict[str, Any]) -> str:
    """Return the per-status counts, in order of first appearance, e.g. "3 check, 1 untested"."""
    counts: dict[str, int] = {}
    for status in coverage.values():
        counts[status] = counts.get(status, 0) + 1
    return ", ".join(f"{n} {status}" for status, n in counts.items())


def validate_rule_coverage(skills_dir: str) -> int:
    """Check eval/verifier/rules.json against the skills' rules; return the problem count."""
    verifier = os.path.join(repo_root_for_skills_dir(skills_dir), "eval/verifier")
    checks_path = os.path.join(verifier, "shared/consult_rules.py")
    coverage, read_problem = read_json_object(os.path.join(verifier, "rules.json"))
    checks_problem = None if os.path.exists(checks_path) else f"missing {checks_path}"
    if read_problem or checks_problem:
        problems = [problem for problem in [read_problem, checks_problem] if problem]
    else:
        problems = rule_coverage_problems(skills_dir, coverage, read_text(checks_path))
    ok_message = f"rule coverage complete ({coverage_summary(coverage)})" if not problems else ""
    return report("rule coverage", problems, "rule coverage problem(s)", ok_message)


# Self-test: the validator run on fixtures that each break one rule.

BAD_FIXTURE = """---
name: bad
model: haiku
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
"""

ROUTER_FIXTURE = """---
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
   | `good` | always |
   | `ghost-skill` | never |
"""

ORPHAN_FIXTURE = """---
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
"""

# A quoted description containing a colon must be measured in full. Reading
# only up to the first inner colon silently under-counts both length budgets.
QUOTED_DESCRIPTION = (
    "Use for design-partner mode: discovery, tradeoffs, decisions, "
    "and the agreed design artifacts that later implementation work binds itself to."
)

QUOTED_FIXTURE = f"""---
name: quoted
description: "{QUOTED_DESCRIPTION}"
---

# Quoted

## When to Use
- trigger

## When NOT to Use
- other

## Rules
1. check
"""

STALE_ROWS = "\n".join(f'| "Shortcut {i}" | Do the thing. | None. |' for i in range(MAX_TRIPWIRE_ROWS + 1))
STALE_FIXTURE = f"""---
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
{STALE_ROWS}

{" ".join(["word"] * MAX_BODY_WORDS)}
"""

BUDGET_FIXTURE = """---
name: budget-{index}
description: {description}
---

# Budget {index}

## When to Use
- trigger

## When NOT to Use
- other

## Rules
1. check
"""

SELF_TEST_EXPECTED = [
    "bad/SKILL.md",
    "frontmatter sets model",
    "When to Use",
    "missing section: ## Rules",
    "description too long",
    "stale/SKILL.md",
    "obsolete section: ## Verification",
    f"Tripwires has {MAX_TRIPWIRE_ROWS + 1} rows",
    "body too long",
    "per <expert>",
    "Common Rationalizations",
    "Red Flags",
    "obsolete table header",
    TRIPWIRES_FORMAT_PROBLEM,
    "em dash found",
    "bad/references/notes.md",
    "canonical sentence",
    "routing table names 'ghost-skill' but no such skill exists",
    "skill 'orphan' is not referenced by the workflow router",
    "description total too long",
    "quoted/SKILL.md",
    f"description too long ({js_length(QUOTED_DESCRIPTION)} > {MAX_DESCRIPTION_LENGTH} characters)",
]


def write_fixture(path: str, text: str) -> None:
    """Write `text` to `path`, creating parent directories."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf8")


def default_skills_dir() -> str:
    """Return this repo's canonical skills directory."""
    return str(Path(__file__).resolve().parent.parent / "agents/.agents/skills")


def write_self_test_fixtures(tmp: str) -> None:
    """Write the self-test skills under `tmp`: the real workflow skill as `good`, and one fixture per rule."""
    shutil.copytree(os.path.join(default_skills_dir(), "workflow"), os.path.join(tmp, "good"))
    write_fixture(os.path.join(tmp, "bad/SKILL.md"), BAD_FIXTURE)
    write_fixture(os.path.join(tmp, "bad/references/notes.md"), "A reference — with an em dash.\n")
    write_fixture(os.path.join(tmp, "workflow/SKILL.md"), ROUTER_FIXTURE)
    write_fixture(os.path.join(tmp, "orphan/SKILL.md"), ORPHAN_FIXTURE)
    write_fixture(os.path.join(tmp, "quoted/SKILL.md"), QUOTED_FIXTURE)
    write_fixture(os.path.join(tmp, "stale/SKILL.md"), STALE_FIXTURE)
    # Enough fixtures to exceed MAX_TOTAL_DESCRIPTION_LENGTH with margin, so the
    # budget assertion does not quietly stop testing anything when the ceiling
    # is raised.
    for index in range(math.ceil(MAX_TOTAL_DESCRIPTION_LENGTH / 100) + 4):
        text = BUDGET_FIXTURE.format(index=index, description="x" * 100)
        write_fixture(os.path.join(tmp, f"budget-{index}/SKILL.md"), text)


def check_self_test_findings(tmp: str, findings: list[Finding]) -> int:
    """Return 0 when the findings include every expected problem and spare the good skill, else 1."""
    paths = [os.path.relpath(finding.path, tmp) for finding in findings]
    rendered = "\n".join([*paths, *(problem for finding in findings for problem in finding.problems)])
    for expected in SELF_TEST_EXPECTED:
        if expected not in rendered:
            print(f"self-test failed: missing {js_json(expected)} in output", file=sys.stderr)
            print(rendered, file=sys.stderr)
            return 1
    if "good/SKILL.md" in paths:
        print("self-test failed: good skill flagged", file=sys.stderr)
        print(rendered, file=sys.stderr)
        return 1
    return 0


def rule_coverage_self_test(directory: str) -> int:
    """Check rule_coverage_problems on a fixture skill; return 0 when it behaves, else 1."""
    write_fixture(
        os.path.join(directory, "demo/SKILL.md"),
        "---\nname: demo\n---\n\n## Rules\n\n1. One.\n   Continued.\n2. Two.\n\n### Detail\n\n3. Not a rule.\n\n## Handoffs\n",
    )
    coverage = {"demo.1": "check", "demo.3": "untested", "demo.9": "maybe"}
    problems = "\n".join(rule_coverage_problems(directory, coverage, 'CHECKS = {"other.1": x}'))
    for expected in [
        "rule demo.2 has no entry in rules.json",
        "rules.json names demo.3, which is not a rule",
        'rules.json demo.9 has unknown status "maybe"',
        "rules.json marks demo.1 as check but consult_rules.py has no CHECKS entry",
    ]:
        if expected not in problems:
            print(f"self-test failed: missing {js_json(expected)} in rule coverage output", file=sys.stderr)
            print(problems, file=sys.stderr)
            return 1
    clean = rule_coverage_problems(directory, {"demo.1": "check", "demo.2": "judge-only"}, 'CHECKS = {"demo.1": f}')
    if clean:
        print(f"self-test failed: complete rule coverage flagged: {'; '.join(clean)}", file=sys.stderr)
        return 1
    return 0


def run_self_test() -> int:
    """Run the validator on fixtures that each break one rule; return 0 when every finding appears."""
    tmp = tempfile.mkdtemp(prefix="has-skill-validator-")
    try:
        write_self_test_fixtures(tmp)
        if check_self_test_findings(tmp, validate_skills(tmp)) != 0:
            return 1
        if rule_coverage_self_test(os.path.join(tmp, "coverage")) != 0:
            return 1
        print("self-test ok")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str]) -> int:
    """Run the CLI on `argv` (arguments after the program name) and return the exit code.

    Every check runs and reports, so one failure does not hide another.
    Returns 0 when all pass, 1 when any fails, and 2 when the skills
    directory does not exist.
    """
    if "-h" in argv or "--help" in argv:
        print(USAGE)
        return 0
    if "--self-test" in argv:
        return run_self_test()
    arg = next((arg for arg in argv if not arg.startswith("-")), None)
    skills_dir = os.path.abspath(arg if arg is not None else default_skills_dir())
    if not os.path.isdir(skills_dir):
        print(f"not a directory: {skills_dir}", file=sys.stderr)
        return 2
    findings = validate_skills(skills_dir)
    print_skill_findings(skills_dir, findings)
    counts = [
        validate_plugin_drift(skills_dir),
        validate_codex_plugin_package(skills_dir),
        validate_cursor_plugin_package(skills_dir),
        validate_antigravity_plugin_package(skills_dir),
        validate_plugin_hooks(skills_dir),
        validate_rule_coverage(skills_dir),
    ]
    return 1 if findings or any(counts) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
