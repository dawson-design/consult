#!/usr/bin/env python3
"""Sync plugin copies from canonical agent assets.

Writes the plugin/skills mirror and the SessionStart hook in
plugin/hooks/hooks.json. validate_skill_anatomy.py imports the constants and
functions below to check that neither has drifted. Stdlib only, so it runs
with a bare python3.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

# Every committed copy of the canonical skills. Each is regenerated from
# agents/.agents/skills so no mirror can silently drift.
MIRROR_DESTS = ["plugin/skills"]

# The SessionStart hook prints the Consult core. Its text lives in the workflow
# skill, so it also ships in the plugin/skills mirror for readers that never
# run the hook. hooks.json carries the text inline rather than reading a path,
# because the eval passes only hooks.json to Claude Code, and Codex has
# resolved plugin root placeholders differently from Claude Code. The heredoc
# needs a POSIX sh, which is how Claude Code runs hook commands.
HOOK_SOURCE = "agents/.agents/skills/workflow/references/core.md"
HOOK_DEST = "plugin/hooks/hooks.json"
# Every session pays for the hook text, and hosts cap hook output (Claude Code
# at 10,000 characters), so the core stays well below that.
MAX_HOOK_CHARS = 4000
HEREDOC_END = "CONSULT_CORE"
# What JavaScript's String.prototype.trim removes. Unlike Python's strip(), it
# includes the byte-order mark and excludes U+001C to U+001F and U+0085.
JS_WHITESPACE = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"

USAGE = """Usage: python3 scripts/generate_plugin_symlinks.py [repo_root]

Sync every skill mirror (plugin/skills) from agents/.agents/skills, and
generate plugin/hooks/hooks.json from the workflow skill's references/core.md."""


def repo_root_from_script() -> str:
    """Return the repository root: the parent of this script's directory."""
    return str(Path(__file__).resolve().parent.parent)


def display(path: str, root: str) -> str:
    """Return `path` relative to `root` when it lies inside it, else `path` unchanged."""
    rel = os.path.relpath(path, root)
    return rel if rel != "." and not rel.startswith("..") else path


def remove_generated(path: str) -> None:
    """Remove a symlink (not its target) or a whole directory tree."""
    if os.path.islink(path):
        os.unlink(path)
    else:
        shutil.rmtree(path)


def is_link_or_dir(path: str) -> bool:
    """Say whether `path` itself, not following symlinks, is a symlink or a directory."""
    mode = os.lstat(path).st_mode
    return stat.S_ISLNK(mode) or stat.S_ISDIR(mode)


def prune_dest(dest: str, src: str, root: str) -> None:
    """Remove generated entries in `dest` that no longer exist in `src`; warn about real files."""
    if not os.path.exists(dest):
        return
    for name in sorted(os.listdir(dest)):
        entry = os.path.join(dest, name)
        if os.path.exists(os.path.join(src, name)):
            continue
        if is_link_or_dir(entry):
            remove_generated(entry)
            print(f"removed stale plugin entry: {display(entry, root)}")
            continue
        print(f"WARNING: {display(entry, root)} is not a generated directory; leaving in place", file=sys.stderr)


def copy_entry(entry: str, target: str) -> None:
    """Copy `entry` to `target`, keeping symlinks as symlinks rather than following them."""
    if os.path.islink(entry):
        os.symlink(os.readlink(entry), target)
    elif os.path.isdir(entry):
        shutil.copytree(entry, target, symlinks=True)
    else:
        shutil.copy2(entry, target)


def sync_each(src: str, dest: str, root: str) -> int:
    """Replace each entry of `dest` with a fresh copy of the same entry in `src`.

    Returns 0, or 1 without copying further when a target is a real file,
    which is never generated and so is never overwritten.
    """
    for name in sorted(os.listdir(src)):
        entry = os.path.join(src, name)
        target = os.path.join(dest, name)
        if os.path.lexists(target):
            if not is_link_or_dir(target):
                print(f"ERROR: {display(target, root)} exists as a real file/dir; remove it first", file=sys.stderr)
                return 1
            remove_generated(target)
        copy_entry(entry, target)
        print(f"copied {display(entry, root)} -> {display(target, root)}")
    return 0


def js_trim(text: str) -> str:
    """Strip leading and trailing whitespace as JavaScript's trim() does."""
    return text.strip(JS_WHITESPACE)


def hook_text(markdown: str) -> str:
    """Return the text the hook prints for `markdown`: no CRs, no surrounding whitespace."""
    return js_trim(markdown.replace("\r", ""))


def js_length(text: str) -> int:
    """Return the length JavaScript reports for `text` (UTF-16 code units).

    Hosts that cap hook output are JavaScript programs, so the limit is
    measured the way they measure it.
    """
    return len(text.encode("utf-16-le")) // 2


def hook_source_problem(markdown: str) -> str | None:
    """Say why `markdown`, the contents of HOOK_SOURCE, cannot become the hook text.

    Returns a problem phrased to follow the file name, or None when the text
    is usable.
    """
    text = hook_text(markdown)
    if not text:
        return "is empty"
    length = js_length(text)
    if length > MAX_HOOK_CHARS:
        return f"is {length} characters; the SessionStart hook allows {MAX_HOOK_CHARS}"
    if HEREDOC_END in text.split("\n"):
        return f"has a line equal to {HEREDOC_END}, which would end the hook's heredoc"
    return None


def render_session_start_hooks(markdown: str) -> str:
    """Render hooks.json: one SessionStart command that prints `markdown`.

    The command uses a quoted heredoc, so the shell expands nothing in the
    text. Check hook_source_problem first. Returns the full file text,
    newline-terminated, formatted as JavaScript's JSON.stringify(_, null, 2).
    """
    command = f"cat <<'{HEREDOC_END}'\n{hook_text(markdown)}\n{HEREDOC_END}"
    hooks = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}}
    return json.dumps(hooks, indent=2, ensure_ascii=False) + "\n"


def sync_session_start_hook(root: str) -> int:
    """Write HOOK_DEST from HOOK_SOURCE under `root`; return 0, or 1 when the source is unusable.

    A root without the hook source (a test fixture, say) keeps whatever
    hooks.json it has; the validator reports a missing source in the real repo.
    """
    source = os.path.join(root, HOOK_SOURCE)
    if not os.path.exists(source):
        print(f"no {HOOK_SOURCE}; left {HOOK_DEST} unchanged")
        return 0
    markdown = Path(source).read_text(encoding="utf8")
    problem = hook_source_problem(markdown)
    if problem:
        print(f"ERROR: {HOOK_SOURCE} {problem}", file=sys.stderr)
        return 1
    dest = Path(root, HOOK_DEST)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_session_start_hooks(markdown), encoding="utf8")
    print(f"generated {HOOK_DEST} from {HOOK_SOURCE}")
    return 0


def sync_plugin_symlinks(repo_root: str) -> int:
    """Regenerate every mirror and the hook under `repo_root`.

    Returns 0 on success, 1 when a real file blocks a copy or the hook source
    is unusable, and 2 when `repo_root` has no agents/.agents/skills directory.
    """
    root = os.path.abspath(repo_root)
    skills_src = os.path.join(root, "agents/.agents/skills")
    if not os.path.exists(skills_src) or not stat.S_ISDIR(os.lstat(skills_src).st_mode):
        print(f"not a repo root (no agents/.agents/skills): {root}", file=sys.stderr)
        return 2
    for dest in MIRROR_DESTS:
        skills_dest = os.path.join(root, dest)
        os.makedirs(skills_dest, exist_ok=True)
        prune_dest(skills_dest, skills_src, root)
        result = sync_each(skills_src, skills_dest, root)
        if result != 0:
            return result
    print("plugin skill mirror in sync")
    return sync_session_start_hook(root)


def main(argv: list[str]) -> int:
    """Run the CLI on `argv` (arguments after the program name) and return the exit code."""
    if "-h" in argv or "--help" in argv:
        print(USAGE)
        return 0
    return sync_plugin_symlinks(argv[0] if argv else repo_root_from_script())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
