#!/usr/bin/env python3
"""Check core.md and every skill against the v2 anatomy and size caps.

The caps keep Consult cheap: core.md is printed into every session, and a
loaded skill stays in context for the rest of it. AGENTS.md explains the
rules this script enforces. build_plugin.py derives the plugin from the same
sources. Stdlib only, so it runs with a bare python3.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agents/.agents/core.md"
SKILLS = ROOT / "agents/.agents/skills"

CORE_MAX_WORDS = 1000
# Claude Code shows only a preview of hook output past 10,000 characters.
CORE_MAX_CHARS = 9000
# eval/scripts/triggers.py detects the hook by this opening.
CORE_OPENING = "Consult is installed."
SKILL_MAX_WORDS = 900
REFERENCE_MAX_WORDS = 1000
MAX_RULES = 10
# Claude Code's skill listing truncates longer descriptions.
DESCRIPTION_MAX_CHARS = 1024
BANNED_HEADINGS = ("Handoffs", "Tripwires", "Red Flags", "Common Rationalizations")
# Emphasis makes current models over-apply a rule; state it plainly instead.
EMPHATIC = re.compile(r"\b(MUST|NEVER|ALWAYS|CRITICAL|IMPORTANT|REQUIRED)\b")
WORD = re.compile(r"[A-Za-z][\w'./-]*")
REFERENCE_MENTION = re.compile(r"references/([\w.-]+\.md)")


@dataclass(frozen=True)
class Skill:
    """A parsed SKILL.md: its directory name, frontmatter fields, and body."""

    dir_name: str
    fields: dict[str, str]
    body: str


def word_count(text: str) -> int:
    """Return the number of prose words in `text`, ignoring Markdown markers."""
    return len(WORD.findall(text))


def parse_skill(path: Path) -> Skill | str:
    """Parse a SKILL.md into a Skill, or return a problem string on bad frontmatter.

    Only top-level `key: value` lines are read; list values such as `paths:`
    are kept as an empty string, which is all the checks need.
    """
    text = path.read_text(encoding="utf8")
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < 3:
        return f"{path.parent.name}: SKILL.md has no frontmatter"
    fields = {}
    for line in parts[1].splitlines():
        match = re.match(r"^([a-z][\w-]*):\s*(.*)$", line)
        if match:
            fields[match[1]] = match[2].strip().strip('"')
    return Skill(path.parent.name, fields, parts[2])


def check_core(text: str) -> list[str]:
    """Return problems with core.md's opening, size, and wording."""
    problems = []
    if not text.startswith(CORE_OPENING):
        problems.append(f"core.md must open with {CORE_OPENING!r}")
    if word_count(text) > CORE_MAX_WORDS:
        problems.append(f"core.md has {word_count(text)} words, cap {CORE_MAX_WORDS}")
    if len(text) > CORE_MAX_CHARS:
        problems.append(f"core.md has {len(text)} characters, cap {CORE_MAX_CHARS}")
    problems.extend(f"core.md: emphatic word {word}" for word in EMPHATIC.findall(text))
    return problems


def check_frontmatter(skill: Skill) -> list[str]:
    """Return problems with a skill's name and description."""
    name, description = skill.fields.get("name", ""), skill.fields.get("description", "")
    problems = []
    if name != skill.dir_name:
        problems.append(f"{skill.dir_name}: frontmatter name is {name!r}")
    if not description:
        problems.append(f"{skill.dir_name}: description is empty")
    if len(description) > DESCRIPTION_MAX_CHARS:
        problems.append(f"{skill.dir_name}: description over {DESCRIPTION_MAX_CHARS} characters")
    if description.lower().startswith("load") or "load before" in description.lower():
        problems.append(f"{skill.dir_name}: description gives an order; say what the skill does and when")
    return problems


def check_body(skill: Skill) -> list[str]:
    """Return problems with a skill's sections, rule count, size, and wording."""
    body, name = skill.body, skill.dir_name
    problems = []
    if not re.search(r"^## Iron law\n\n\S", body, re.MULTILINE):
        problems.append(f"{name}: needs an '## Iron law' section with the law as its first paragraph")
    rules = re.search(r"^## Rules\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if not rules:
        problems.append(f"{name}: needs a '## Rules' section")
    elif len(re.findall(r"^\d+\. ", rules[1], re.MULTILINE)) > MAX_RULES:
        problems.append(f"{name}: more than {MAX_RULES} rules")
    problems.extend(
        f"{name}: banned section '{h}'" for h in BANNED_HEADINGS if re.search(rf"^## {h}\b", body, re.MULTILINE)
    )
    problems.extend(f"{name}: emphatic word {word}" for word in EMPHATIC.findall(body))
    if word_count(body) > SKILL_MAX_WORDS:
        problems.append(f"{name}: {word_count(body)} words, cap {SKILL_MAX_WORDS}")
    return problems


def check_references(skill_dir: Path, body: str) -> list[str]:
    """Return problems linking SKILL.md to its references/ directory."""
    name = skill_dir.name
    ref_dir = skill_dir / "references"
    present = {p.name for p in ref_dir.iterdir()} if ref_dir.is_dir() else set()
    mentioned = set(REFERENCE_MENTION.findall(body))
    problems = [f"{name}: references/{ref} is listed but missing" for ref in sorted(mentioned - present)]
    problems += [f"{name}: references/{ref} is never listed in SKILL.md" for ref in sorted(present - mentioned)]
    for ref in sorted(present):
        path = ref_dir / ref
        if path.is_dir():
            problems.append(f"{name}: references/{ref} is nested; keep references one level deep")
        elif word_count(path.read_text(encoding="utf8")) > REFERENCE_MAX_WORDS:
            problems.append(f"{name}: references/{ref} over {REFERENCE_MAX_WORDS} words")
    return problems


def check_skill(skill_dir: Path) -> list[str]:
    """Return every problem found in one skill directory."""
    path = skill_dir / "SKILL.md"
    if not path.exists():
        return [f"{skill_dir.name}: no SKILL.md"]
    skill = parse_skill(path)
    if isinstance(skill, str):
        return [skill]
    return check_frontmatter(skill) + check_body(skill) + check_references(skill_dir, skill.body)


def validate(core: Path = CORE, skills: Path = SKILLS) -> list[str]:
    """Return every problem in core.md and the skills directory."""
    problems = check_core(core.read_text(encoding="utf8"))
    for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
        problems.extend(check_skill(skill_dir))
    return problems


def main() -> int:
    problems = validate()
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
