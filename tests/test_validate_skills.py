"""Tests for scripts/validate_skills.py. Each failure case starts from a valid
skill pack in a temp directory and breaks one thing, so a passing test shows
that one check catches that one fault."""

from pathlib import Path

import pytest
import validate_skills

CORE = "Consult is installed. Skills load by topic.\n\n# Consult core\n\nKeep it simple.\n"
SKILL = """---
name: demo
description: "Does a demo thing. Use when demoing."
---

# Demo

## Iron law

Demos stay small.

## Rules

1. Keep the demo short.

## References

- `references/notes.md`: read when you need notes.
"""


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """Write a valid core.md and one valid skill with one reference."""
    (tmp_path / "core.md").write_text(CORE)
    refs = tmp_path / "skills/demo/references"
    refs.mkdir(parents=True)
    (refs / "notes.md").write_text("# Notes\n\nSome notes.\n")
    (tmp_path / "skills/demo/SKILL.md").write_text(SKILL)
    return tmp_path


def problems(pack: Path) -> list[str]:
    return validate_skills.validate(pack / "core.md", pack / "skills")


def edit_skill(pack: Path, old: str, new: str) -> None:
    path = pack / "skills/demo/SKILL.md"
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))


def test_valid_pack_has_no_problems(pack: Path) -> None:
    assert problems(pack) == []


def test_real_sources_have_no_problems() -> None:
    assert validate_skills.validate() == []


def test_core_must_open_with_the_trigger_phrase(pack: Path) -> None:
    (pack / "core.md").write_text("# Consult core\n")

    assert any("must open with" in p for p in problems(pack))


def test_core_word_cap(pack: Path) -> None:
    (pack / "core.md").write_text(CORE + "word " * validate_skills.CORE_MAX_WORDS)

    assert any("core.md has" in p and "words" in p for p in problems(pack))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("name: demo", "name: other", "frontmatter name"),
        ('"Does a demo thing. Use when demoing."', '"Load before editing demos."', "gives an order"),
        ("## Iron law\n\nDemos stay small.\n", "", "Iron law"),
        ("## Rules\n", "## Steps\n", "'## Rules'"),
        ("1. Keep the demo short.", "\n".join(f"{n}. Rule." for n in range(1, 12)), "more than 10 rules"),
        ("## References", "## Handoffs\n\n- x\n\n## References", "banned section 'Handoffs'"),
        ("Keep the demo short.", "You MUST keep the demo short.", "emphatic word MUST"),
        ("`references/notes.md`", "`references/missing.md`", "missing.md is listed but missing"),
    ],
)
def test_skill_fault_is_reported(pack: Path, old: str, new: str, expected: str) -> None:
    edit_skill(pack, old, new)

    assert any(expected in p for p in problems(pack)), problems(pack)


def test_unlisted_reference_is_reported(pack: Path) -> None:
    (pack / "skills/demo/references/extra.md").write_text("extra\n")

    assert any("extra.md is never listed" in p for p in problems(pack))


def test_skill_word_cap(pack: Path) -> None:
    edit_skill(pack, "Keep the demo short.", "word " * validate_skills.SKILL_MAX_WORDS)

    assert any("words, cap" in p for p in problems(pack))
