#!/usr/bin/env python3
"""Draw the release chart from a lift summary: each task's reward, bare against Consult.

  python3 eval/scripts/charts.py eval/results/<date>-release.json assets/charts "Claude Code"

lift.py writes the summary as eval/runs/lift/<job>.json; a release copies it
to eval/results/ next to its results file, since runs/ is not tracked. This
writes release-lift-<agent>-light.svg and release-lift-<agent>-dark.svg to the
output dir, for the README's <picture> element. Regenerate them from each
release's summary rather than editing the SVGs.

The chart is a dumbbell per task the suite lift scored, sorted by lift: a
hollow gray ring for the bare agent and a filled brand-orange dot for Consult,
so the arms differ by shape as well as colour and a tie shows the dot inside
the ring. The footer gives the suite lift with its 90% interval and notes any
task left out, failed trial, or judge exclusion that lift.py reported. The two
marker colours pass the dataviz palette validator's separation and contrast
checks on GitHub's light (#ffffff) and dark (#0d1117) surfaces, and each SVG
paints its own surface. Text uses ink colours, never a series colour, and the
per-task numbers live in the results file's table. Standard library only, so
the tests run in CI.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

LIGHT = {"name": "light", "surface": "#ffffff", "primary": "#0b0b0b", "secondary": "#52514e",
         "grid": "#e1e0d9", "connector": "#c3c2b7", "bare": "#898781", "consult": "#e8592f"}
DARK = {"name": "dark", "surface": "#0d1117", "primary": "#ffffff", "secondary": "#c3c2b7",
        "grid": "#2c2c2a", "connector": "#4a4a46", "bare": "#898781", "consult": "#e8592f"}
FONT = "-apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif"
LABEL_SIZE, EM_PER_CHAR = 13, 0.62  # a wide estimate, so labels fit fonts wider than Helvetica
MARGIN, PLOT_WIDTH, RIGHT_MARGIN = 16, 480, 48
TOP, ROW_HEIGHT, MARKER_RADIUS = 76, 28, 5
TICKS = (0.0, 0.25, 0.5, 0.75, 1.0)
LABEL_GAP = 64  # top-row markers closer than this get no direct labels
NAMED_LEFT_OUT = 3  # the footer names this many left-out tasks, then counts the rest


@dataclass(frozen=True)
class Layout:
    """Where the plot sits: the label column is as wide as the longest task name needs."""

    plot_left: float
    rows: int

    @property
    def width(self) -> float:
        return self.plot_left + PLOT_WIDTH + RIGHT_MARGIN

    @property
    def bottom(self) -> float:
        return TOP + (self.rows - 1) * ROW_HEIGHT + 16

    def x(self, reward: float) -> float:
        """Horizontal position of a reward between 0 and 1."""
        return self.plot_left + reward * PLOT_WIDTH


def label_width(name: str) -> float:
    """A generous estimate of a task label's rendered width in px."""
    return len(name) * LABEL_SIZE * EM_PER_CHAR


def task_name(task: str) -> str:
    return task.split("/")[-1]


def scored_rows(summary: dict) -> list[dict]:
    """The rows the suite lift scored, sorted by lift; SystemExit when the summary cannot be drawn."""
    scored = set(summary["suite"]["tasks"])
    rows = [r for r in summary["tasks"] if r["task"] in scored]
    if not rows:
        raise SystemExit("the summary has no task that both arms ran")
    bad = [r["task"] for r in rows if not all(0.0 <= r[arm] <= 1.0 for arm in ("bare", "consult"))]
    if bad:
        raise SystemExit(f"rewards outside 0 to 1 for {', '.join(bad)}")
    return sorted(rows, key=lambda r: r["consult"] - r["bare"], reverse=True)


def signed(value: float) -> str:
    """A signed two-decimal number that never prints as -0.00."""
    return f"{0.0 if round(value, 2) == 0 else value:+.2f}"


def caption(summary: dict) -> str:
    """The suite lift over the tasks it scored, with its interval."""
    suite = summary["suite"]
    interval = suite.get("reward_interval")
    spread = "no interval" if not interval else f"90% interval {signed(interval[0])} to {signed(interval[1])}"
    return f"Suite lift {signed(suite['reward'])} across {len(suite['tasks'])} tasks ({spread})"


def footnotes(summary: dict, rows: list[dict]) -> list[str]:
    """The caveats lift.py reports that a reader of the chart alone would miss, each short enough for one line."""
    notes = []
    missing = [task_name(t) for t in summary["suite"].get("missing") or []]
    if missing:
        named = ", ".join(missing[:NAMED_LEFT_OUT])
        more = f", and {len(missing) - NAMED_LEFT_OUT} more" if len(missing) > NAMED_LEFT_OUT else ""
        notes.append(f"Left out, no bare trials ({len(missing)}): {named}{more}")
    failed = sum(len(r.get("failed") or []) for r in rows)
    if failed:
        notes.append(f"{failed} failed trial{'s' if failed > 1 else ''} in the plotted tasks; see the results file")
    if summary.get("judge_excluded"):
        notes.append("Rewards exclude the judge: one arm ran without it")
    return notes


def text(x: float, y: float, content: str, fill: str, size: int = LABEL_SIZE, anchor: str = "start",
         css_class: str = "", weight: int = 400) -> str:
    """An SVG text element with its content escaped."""
    attrs = f' class="{css_class}"' if css_class else ""
    return (f'<text{attrs} x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(content)}</text>')


def marker(x: float, y: float, arm: str, theme: dict, css_class: str = "") -> str:
    """A hollow ring for bare, a filled dot for Consult; the surface ring keeps overlapping dots apart."""
    css = css_class or arm
    if arm == "bare":
        return (f'<circle class="{css}" cx="{x:.1f}" cy="{y:.1f}" r="{MARKER_RADIUS + 1}" fill="none" '
                f'stroke="{theme["bare"]}" stroke-width="2"/>')
    return (f'<circle class="{css}" cx="{x:.1f}" cy="{y:.1f}" r="{MARKER_RADIUS}" fill="{theme["consult"]}" '
            f'stroke="{theme["surface"]}" stroke-width="2"/>')


def header(title: str, theme: dict) -> list[str]:
    """Title and legend; the legend markers match the plot's."""
    legend_y = 50
    return [text(MARGIN, 26, title, theme["primary"], size=16, weight=600),
            marker(22, legend_y - 4, "bare", theme, css_class="legend"),
            text(34, legend_y, "Bare", theme["secondary"]),
            marker(92, legend_y - 4, "consult", theme, css_class="legend"),
            text(104, legend_y, "Consult", theme["secondary"])]


def grid(layout: Layout, theme: dict) -> list[str]:
    """Hairline gridlines and tick labels at each quarter of the reward scale."""
    lines = []
    for tick in TICKS:
        x = layout.x(tick)
        lines.append(f'<line x1="{x:.1f}" y1="{TOP - 12}" x2="{x:.1f}" y2="{layout.bottom:.1f}" '
                     f'stroke="{theme["grid"]}" stroke-width="1"/>')
        lines.append(text(x, layout.bottom + 16, f"{tick:g}", theme["secondary"], size=12, anchor="middle"))
    return lines


def row(index: int, task: dict, layout: Layout, theme: dict) -> list[str]:
    """One task: its label, the connector, then the Consult dot under the bare ring, so a tie shows both."""
    y = TOP + index * ROW_HEIGHT
    bare_x, consult_x = layout.x(task["bare"]), layout.x(task["consult"])
    return [text(layout.plot_left - MARGIN, y + 4, task_name(task["task"]), theme["secondary"], anchor="end",
                 css_class="task"),
            f'<line x1="{bare_x:.1f}" y1="{y}" x2="{consult_x:.1f}" y2="{y}" stroke="{theme["connector"]}" '
            f'stroke-width="2"/>',
            marker(consult_x, y, "consult", theme), marker(bare_x, y, "bare", theme)]


def direct_labels(task: dict, layout: Layout, theme: dict) -> list[str]:
    """Name both markers above the top row, when they sit far enough apart to keep the labels clear."""
    bare_x, consult_x = layout.x(task["bare"]), layout.x(task["consult"])
    if abs(consult_x - bare_x) < LABEL_GAP:
        return []
    y = TOP - 12
    return [text(bare_x, y, "Bare", theme["secondary"], size=12, anchor="middle", css_class="direct-label"),
            text(consult_x, y, "Consult", theme["secondary"], size=12, anchor="middle", css_class="direct-label")]


def dumbbell_svg(summary: dict, theme: dict, agent: str) -> str:
    """The chart as an SVG document for one theme."""
    rows = scored_rows(summary)
    layout = Layout(plot_left=2 * MARGIN + max(label_width(task_name(r["task"])) for r in rows), rows=len(rows))
    title = f"Reward per task on {agent}: bare agent vs Consult"
    lines = [caption(summary), *footnotes(summary, rows)]
    height = layout.bottom + 40 + 20 * len(lines)
    body = [f'<rect width="100%" height="100%" fill="{theme["surface"]}"/>', *header(title, theme),
            *grid(layout, theme)]
    for index, task in enumerate(rows):
        body += row(index, task, layout, theme)
    body += direct_labels(rows[0], layout, theme)
    body += [text(MARGIN, layout.bottom + 48 + 20 * i, line, theme["secondary"], css_class="footer")
             for i, line in enumerate(lines)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.width:.0f} {height:.0f}" '
            f'width="{layout.width:.0f}" height="{height:.0f}" role="img" aria-labelledby="title desc" '
            f'font-family="{FONT}">\n<title id="title">{escape(title)}</title>\n'
            f'<desc id="desc">{escape(". ".join(lines))}</desc>\n' + "\n".join(body) + "\n</svg>\n")


def slug(agent: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", agent.lower()).strip("-")


def main(argv: list[str]) -> int:
    """charts.py <summary.json> <out_dir> <agent name>: write the light and dark charts."""
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    summary = json.loads(Path(argv[1]).read_text())
    out_dir, agent = Path(argv[2]), argv[3].strip()
    if not slug(agent):
        print("the agent name needs a letter or digit, e.g. \"Claude Code\"", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme in (LIGHT, DARK):
        path = out_dir / f"release-lift-{slug(agent)}-{theme['name']}.svg"
        path.write_text(dumbbell_svg(summary, theme, agent))
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
