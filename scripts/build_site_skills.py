#!/usr/bin/env python3
"""Generate the marketing site's skills page from the repo's own sources.

Reads the Consult core (`agents/.agents/core.md`), the grouped skill list under `## Skills`
in `README.md`, and each skill's Iron Law from its canonical `SKILL.md`, then writes
`site/skills/index.html`. Regenerate after any skill, core, or README skill-list change,
so the page cannot drift from the source. Standard library only, like the rest of `scripts/`.

Usage: python3 scripts/build_site_skills.py [--check]
  --check  exit 1 if the page on disk differs from what would be generated.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "agents/.agents/core.md"
SKILLS_DIR = REPO / "agents/.agents/skills"
README = REPO / "README.md"
OUT = REPO / "site/skills/index.html"
GITHUB = "https://github.com/dawson-design/consult"

RULE_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$")
GROUP_RE = re.compile(r"^- (.+):\s*$")
ITEM_RE = re.compile(r"^\s+- \[`([a-z0-9-]+)`\]\(([^)]+)\):\s*(.+)$")
IRON_RE = re.compile(r"^`(.+)`\s*$")


@dataclass(frozen=True)
class Rule:
    """One numbered core rule: its bold title and the first sentence that follows it."""

    number: int
    title: str
    first_sentence: str


@dataclass(frozen=True)
class Skill:
    """One skill as the README lists it, plus its Iron Law when the skill has one."""

    name: str
    description: str
    iron_law: str | None


def first_sentence(text: str) -> str:
    """Return text up to and including the first sentence-ending period, or all of it."""
    match = re.search(r"^(.+?\.)(\s|$)", text)
    return match.group(1) if match else text


def parse_core(text: str) -> tuple[str, list[Rule]]:
    """Parse core.md into its Iron Law and its numbered rules.

    A rule's text runs from its numbered line until the next numbered line or a blank line;
    wrapped lines are joined. Raises ValueError when the Iron Law or the rules are missing.
    """
    iron = section_iron_law(text)
    if iron is None:
        raise ValueError("core.md has no Iron Law")
    rules: list[Rule] = []
    current: list[str] | None = None
    number, title = 0, ""

    def flush() -> None:
        if current is not None:
            rules.append(Rule(number, title, first_sentence(" ".join(current).strip())))

    for line in text.splitlines():
        match = RULE_RE.match(line)
        if match:
            flush()
            number, title, current = int(match[1]), match[2].rstrip(), [match[3]]
        elif current is not None and line.strip():
            current.append(line.strip())
        elif current is not None:
            flush()
            current = None
    flush()
    if not rules:
        raise ValueError("core.md has no numbered rules")
    return iron, rules


def section_iron_law(text: str) -> str | None:
    """Return the backticked line under `## Iron Law`, or None when there is none."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Iron Law":
            for follow in lines[i + 1 :]:
                if follow.startswith("## "):
                    return None
                match = IRON_RE.match(follow.strip())
                if match:
                    return match[1]
    return None


def parse_readme_skills(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return the README's `## Skills` list as [(group, [(skill name, description)])]."""
    body = text.split("\n## Skills\n", 1)
    if len(body) < 2:
        raise ValueError("README.md has no '## Skills' section")
    section = body[1].split("\n## ", 1)[0]
    groups: list[tuple[str, list[tuple[str, str]]]] = []
    for line in section.splitlines():
        group = GROUP_RE.match(line)
        item = ITEM_RE.match(line)
        if group:
            groups.append((group[1], []))
        elif item and groups:
            groups[-1][1].append((item[1], item[3].strip()))
    return groups


def load_skills(groups: list[tuple[str, list[tuple[str, str]]]]) -> list[tuple[str, list[Skill]]]:
    """Attach each listed skill's Iron Law, and check the list covers every skill directory.

    Raises ValueError naming any skill directory the README leaves out, any listed skill with no
    SKILL.md, or any skill listed twice, so the page fails to build rather than drift from the
    source.
    """
    on_disk = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    names = [name for _, items in groups for name, _ in items]
    listed = set(names)
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"README lists skills more than once: {', '.join(repeated)}")
    if on_disk - listed:
        raise ValueError(f"README skill list is missing: {', '.join(sorted(on_disk - listed))}")
    if listed - on_disk:
        raise ValueError(f"README lists skills with no SKILL.md: {', '.join(sorted(listed - on_disk))}")
    return [
        (
            group,
            [
                Skill(name, desc, section_iron_law((SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")))
                for name, desc in items
            ],
        )
        for group, items in groups
    ]


ACRONYMS = {"openapi": "OpenAPI", "pii": "PII", "wcag": "WCAG", "aa": "AA"}


def sentence_case(text: str) -> str:
    """Turn an all-caps Iron Law into sentence case, keeping known acronyms in their usual form.

    Each sentence (after a period and space) starts with a capital; everything else is lower
    case except the words in ACRONYMS.
    """
    lowered = re.sub(r"[a-z]+", lambda m: ACRONYMS.get(m[0], m[0]), text.lower())
    return re.sub(r"(^|\.\s+)([a-z])", lambda m: m[1] + m[2].upper(), lowered)


def joiner(continuation: str) -> str:
    """Space between a rule's bold title and its text, except before punctuation that continues it."""
    return "" if continuation[:1] in ",;:." else " "


def inline(text: str) -> str:
    """Escape text for HTML, then render Markdown `code` spans as <code>."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text, quote=False))


def render(iron: str, rules: list[Rule], groups: list[tuple[str, list[Skill]]]) -> str:
    """Render the full skills page as an HTML document string."""
    count = sum(len(items) for _, items in groups)
    rule_items = "\n".join(
        f"<li><b>{inline(r.title)}</b>{joiner(r.first_sentence)}{inline(r.first_sentence)}</li>" for r in rules
    )
    group_blocks = []
    for group, items in groups:
        entries = []
        for skill in items:
            law = f'<p class="law">{inline(sentence_case(skill.iron_law))}</p>' if skill.iron_law else ""
            href = f"{GITHUB}/blob/main/agents/.agents/skills/{skill.name}/SKILL.md"
            entries.append(
                f'<dt><a href="{href}"><code>{skill.name}</code></a></dt><dd><p>{inline(skill.description)}</p>{law}</dd>'
            )
        group_blocks.append(f'<h3>{inline(group)}</h3>\n<dl class="glossary">{"".join(entries)}</dl>')
    return PAGE.format(
        rule_count=len(rules),
        skill_count=count,
        iron=inline(sentence_case(iron)),
        rules=rule_items,
        groups="\n".join(group_blocks),
        github=GITHUB,
    )


PAGE = """<!doctype html>
<!-- Generated by scripts/build_site_skills.py from core.md, README.md, and each SKILL.md. Do not edit by hand. -->
<html lang="en" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Consult Skills</title>
<meta name="description" content="The {rule_count} core rules and {skill_count} skills in Consult, the open-source skills and workflow plugin for coding agents.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@800..900&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="../base.css">
<link rel="stylesheet" href="../site.css">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs><g id="q-open" transform="translate(0 10)"><path d="M18 20 H30 V32 A12 12 0 0 1 18 44 Z" transform="rotate(180 24 32)"/><path d="M34 20 H46 V32 A12 12 0 0 1 34 44 Z" transform="rotate(180 40 32)"/></g><g id="q-close" transform="translate(-2.5 -10)"><path d="M54 56 H66 V68 A12 12 0 0 1 54 80 Z"/><path d="M70 56 H82 V68 A12 12 0 0 1 70 80 Z"/></g></defs></svg>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap wrap-wide top-inner">
<a class="brand" href="../" aria-label="Consult home"><svg class="logo" viewBox="18 30 61.5 40" aria-hidden="true" focusable="false"><use href="#q-open" class="q-open"/><use href="#q-close" class="q-close"/></svg>consult</a>
<nav class="nav" aria-label="Main"><a href="../#how">How it works</a><a href="./" aria-current="page">Skills</a><a class="star" href="{github}"><svg class="gh" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>Star on GitHub</a></nav>
</div></header>
<main id="main">
<article class="catalog"><div class="wrap wrap-wide catalog-grid">
<div class="catalog-text">
<h1>Skills and core rules</h1>
<p class="section-lead">{rule_count} core rules apply to every change, whether or not a skill loads. The workflow skill then loads only the skills that match the task, from these {skill_count}.</p>
<h2 id="core-title">Core rules</h2>
<p class="law law-lead">{iron}</p>
<ol class="rules">
{rules}
</ol>
<h2 id="skills-title">{skill_count} skills</h2>
{groups}
</div>
<aside class="rail-col" aria-hidden="true"><canvas class="hex-rail"></canvas></aside>
</div></article>
</main>
<footer class="foot"><div class="wrap wrap-wide foot-inner">
<a class="brand" href="../" aria-label="Consult home"><svg class="logo" viewBox="18 30 61.5 40" aria-hidden="true" focusable="false"><use href="#q-open" class="q-open"/><use href="#q-close" class="q-close"/></svg>consult</a>
<ul><li><a href="{github}">Source</a></li><li><a href="{github}/blob/main/CHANGELOG.md">Changelog</a></li><li><a href="{github}/issues">Issues</a></li><li><a href="{github}/blob/main/LICENSE">MIT licence</a></li></ul>
<p class="credit">© 2026 Dawson Design Ltd.</p></div></footer>
<script>document.documentElement.classList.remove('no-js');</script>
<script src="../rail.js" defer></script>
</body>
</html>
"""


def build() -> str:
    """Read the sources and return the generated page."""
    iron, rules = parse_core(CORE.read_text(encoding="utf-8"))
    groups = load_skills(parse_readme_skills(README.read_text(encoding="utf-8")))
    return render(iron, rules, groups)


def main() -> int:
    """Write the page, or with --check compare it with the file on disk. Returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the page on disk is stale")
    args = parser.parse_args()
    try:
        page = build()
    except ValueError as error:
        print(f"build_site_skills: {error}", file=sys.stderr)
        return 1
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != page:
            print(f"{OUT.relative_to(REPO)} is stale; run scripts/build_site_skills.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
