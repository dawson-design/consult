#!/usr/bin/env python3
"""Generate the marketing site's skills page from the repo's own sources.

Reads the Consult core (`agents/.agents/core.md`): its opening principle and its three numbered
sections, Rules, House defaults, and Working with the human. Reads each skill's name,
description, and invocation flag from its `SKILL.md` frontmatter, and its iron law. Writes `site/skills/index.html`.
Regenerate after any skill or core change, so the page cannot drift from the source; the site
tests fail while it is stale. Standard library only, like the rest of `scripts/`.

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
OUT = REPO / "site/skills/index.html"
GITHUB = "https://github.com/dawson-design/consult"
SECTIONS = ("Rules", "House defaults", "Working with the human")

ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)$")
BULLET_RE = re.compile(r"^\s+- (.*)$")

Block = str | tuple[str, ...]
"""A paragraph of an item, or a bullet list inside it."""


@dataclass(frozen=True)
class Item:
    """One numbered item in a core section: its number and its paragraphs and bullet lists."""

    number: int
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Section:
    """One core section: the text before its first item, and its items."""

    intro: str
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Core:
    """The parsed core: its opening principle and its sections by heading."""

    principle: str
    sections: dict[str, Section]


@dataclass(frozen=True)
class Skill:
    """One skill: its frontmatter fields and its iron law, when it has one."""

    name: str
    description: str
    invoked_only: bool
    iron_law: str | None


def parse_core(text: str) -> Core:
    """Parse core.md into its principle (the paragraph under `# Consult core`) and sections.

    Raises ValueError when the principle or one of SECTIONS is missing or has no items.
    """
    after_title = text.split("\n# Consult core\n", 1)
    if len(after_title) < 2:
        raise ValueError("core.md has no '# Consult core' heading")
    parts = re.split(r"^## (.+)$", after_title[1], flags=re.MULTILINE)
    principle = " ".join(parts[0].split())
    if not principle:
        raise ValueError("core.md has no principle under '# Consult core'")
    found = {parts[i].strip(): parse_section(parts[i + 1]) for i in range(1, len(parts), 2)}
    missing = [name for name in SECTIONS if name not in found or not found[name].items]
    if missing:
        raise ValueError(f"core.md has no numbered items under: {', '.join(missing)}")
    return Core(principle, {name: found[name] for name in SECTIONS})


def parse_section(text: str) -> Section:
    """Split a section into its intro and its numbered items.

    An item runs until the next numbered line or a line that is not indented. Inside it, a blank
    line starts a new paragraph and `- ` lines form a bullet list; wrapped lines are joined.
    """
    intro: list[str] = []
    items: list[tuple[int, list[list[str]]]] = []
    for line in text.splitlines():
        item = ITEM_RE.match(line)
        if item:
            items.append((int(item[1]), [[item[2]]]))
        elif not items:
            intro.append(line)
        elif not line.strip():
            items[-1][1].append([])
        elif line.startswith(" "):
            add_line(items[-1][1], line)
    return Section(" ".join(" ".join(intro).split()), tuple(Item(n, to_blocks(raw)) for n, raw in items))


def add_line(raw: list[list[str]], line: str) -> None:
    """Add an indented line to an item's raw blocks: a new bullet, or a continuation."""
    bullet = BULLET_RE.match(line)
    if bullet:
        raw.append(["- " + bullet[1]])
    else:
        raw[-1].append(line.strip())


def to_blocks(raw: list[list[str]]) -> tuple[Block, ...]:
    """Join raw lines into paragraphs, and runs of bullets into one bullet list each."""
    blocks: list[Block] = []
    for lines in raw:
        if not lines:
            continue
        joined = " ".join(lines)
        if joined.startswith("- "):
            previous = blocks[-1] if blocks else None
            bullets = previous if isinstance(previous, tuple) else ()
            if bullets:
                blocks.pop()
            blocks.append((*bullets, joined[2:]))
        else:
            blocks.append(joined)
    return tuple(blocks)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return a SKILL.md's frontmatter as plain key/value strings, with quotes removed."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise ValueError("SKILL.md has no frontmatter")
    fields: dict[str, str] = {}
    for line in match[1].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def iron_law(text: str) -> str | None:
    """Return the paragraph under a SKILL.md's `## Iron law` heading, or None when there is none."""
    match = re.search(r"^## Iron law\n+(.+?)(?:\n\n|\n## |\Z)", text, re.MULTILINE | re.DOTALL)
    return " ".join(match[1].split()) if match else None


def load_skills() -> list[Skill]:
    """Read every skill directory's frontmatter, sorted by name.

    Raises ValueError when a skill has no name or description.
    """
    skills = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        if not fields.get("name") or not fields.get("description"):
            raise ValueError(f"{path.relative_to(REPO)} needs a name and a description")
        invoked = fields.get("disable-model-invocation") == "true"
        skills.append(Skill(fields["name"], fields["description"], invoked, iron_law(text)))
    return skills


def inline(text: str) -> str:
    """Escape text for HTML, then render Markdown `code` spans and **bold** runs."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def render_item(item: Item) -> str:
    """Render one item as an <li> that keeps its own number, since sections can skip numbers."""
    parts = []
    for block in item.blocks:
        if isinstance(block, tuple):
            parts.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in block) + "</ul>")
        else:
            parts.append(inline(block) if not parts else f"<p>{inline(block)}</p>")
    return f'<li value="{item.number}">{"".join(parts)}</li>'


def law(text: str | None) -> str:
    """Render a skill's iron law under its description, or nothing when it has none."""
    return f'<p class="law">{inline(text)}</p>' if text else ""


def render_skills(skills: list[Skill]) -> str:
    """Render the skills in two groups: those that load by topic, and those you invoke."""
    groups = [
        ("Load when their topic comes up", [s for s in skills if not s.invoked_only]),
        ("Run when you invoke them", [s for s in skills if s.invoked_only]),
    ]
    blocks = []
    for title, members in groups:
        entries = "".join(
            f'<dt><a href="{GITHUB}/blob/main/agents/.agents/skills/{s.name}/SKILL.md"><code>{s.name}</code></a></dt>'
            f"<dd><p>{inline(s.description)}</p>{law(s.iron_law)}</dd>"
            for s in members
        )
        blocks.append(f'<h3>{title}</h3>\n<dl class="glossary">{entries}</dl>')
    return "\n".join(blocks)


def render(core: Core, skills: list[Skill]) -> str:
    """Render the full skills page as an HTML document string."""
    rules, defaults, human = (core.sections[name] for name in SECTIONS)
    return PAGE.format(
        rule_count=len(rules.items),
        default_count=len(defaults.items),
        human_count=len(human.items),
        skill_count=len(skills),
        iron=inline(core.principle),
        rules="\n".join(render_item(i) for i in rules.items),
        defaults_intro=inline(defaults.intro),
        defaults="\n".join(render_item(i) for i in defaults.items),
        human_intro=inline(human.intro),
        human="\n".join(render_item(i) for i in human.items),
        groups=render_skills(skills),
        github=GITHUB,
    )


PAGE = """<!doctype html>
<!-- Generated by scripts/build_site_skills.py from core.md and each SKILL.md. Do not edit by hand. -->
<html lang="en" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Consult Skills</title>
<meta name="description" content="The {rule_count} core rules, {default_count} house defaults, and {skill_count} skills in Consult, the open-source skills plugin for coding agents.">
<title>Consult Skills</title>
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
<nav class="nav" aria-label="Main"><a href="./" aria-current="page">Skills</a><a href="../why/">Why Consult</a><a class="star" href="{github}"><svg class="gh" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>GitHub</a></nav>
</div></header>
<main id="main">
<article class="catalog"><div class="wrap wrap-wide catalog-grid">
<div class="catalog-text">
<h1>Skills and core rules</h1>
<p class="section-lead">Every rule serves one Iron Law: complexity is the enemy. The core prints at the start of every session: {rule_count} core rules, {default_count} house defaults, and {human_count} rules for working with you. The <a href="#skills-title">{skill_count} skills</a> load only when their topic comes up or when you invoke them.</p>
<h2 id="core-title">Core rules</h2>
<p class="law-label">Iron Law</p>
<p class="law law-lead">{iron}</p>
<ol class="rules">
{rules}
</ol>
<h2 id="defaults-title">House defaults</h2>
<p>{defaults_intro}</p>
<ol class="rules">
{defaults}
</ol>
<h2 id="human-title">Working with you</h2>
<p>{human_intro}</p>
<ol class="rules">
{human}
</ol>
<h2 id="skills-title">{skill_count} skills</h2>
{groups}
</div>
</div></article>
</main>
<footer class="foot"><div class="wrap wrap-wide foot-inner">
<a class="brand" href="../" aria-label="Consult home"><svg class="logo" viewBox="18 30 61.5 40" aria-hidden="true" focusable="false"><use href="#q-open" class="q-open"/><use href="#q-close" class="q-close"/></svg>consult</a>
<ul><li><a href="{github}">Source</a></li><li><a href="{github}/blob/main/CHANGELOG.md">Changelog</a></li><li><a href="{github}/issues">Issues</a></li><li><a href="{github}/blob/main/LICENSE">MIT licence</a></li></ul>
<p class="credit">© 2026 Dawson Design Ltd.</p></div></footer>
<script>document.documentElement.classList.remove('no-js');</script>
</body>
</html>"""


def build() -> str:
    """Read the sources and return the generated page."""
    return render(parse_core(CORE.read_text(encoding="utf-8")), load_skills())


def main() -> int:
    """Write the page, or with --check compare it with the file on disk. Returns the exit code."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
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
