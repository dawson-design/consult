# Maintaining Consult

This guide covers editing Consult itself. The rules the agent follows live in
`agents/.agents/core.md` and `agents/.agents/skills/`. `plugin/` is generated
from them by `make plugin`, so never edit it by hand.

## The test for every line

Keep a line only when it answers "which choice?" for a decision where a strong
engineer could reasonably go either way, or when it states a floor that models
measurably miss: a threshold, a trap, a dated fact. Cut lines that teach what
a practice is, restate common practice, or repeat another rule.

Evidence behind this:
- In v1, only rules that picked a side or set a floor showed lift.
- SWE-Skills-Bench found 92 of 98 public skills had no effect.
- SkillsBench found compact skills gain more than comprehensive ones.

## Wording

- **Prefer constraints with one escape hatch:** "Don't X; do Y, unless the
  project already does Z." In the Guardrails Beat Guidance study, every
  individually helpful rule was a negative constraint.
- **Write calmly:** no MUST, NEVER, ALWAYS, CRITICAL, or IMPORTANT in capitals.
  Current models over-apply emphatic rules. The validator rejects them.
- **Iron laws are one sentence-case line.**
- **Descriptions are third person** and say what the skill does, then "Use
  when ...". Don't write them as orders ("Load before ...").

## Shape and caps (enforced by `scripts/validate_skills.py`)

- `core.md`:
  - At most 1,000 words and 9,000 characters, since it prints every session.
  - It opens with "Consult is installed.", which the trigger eval detects.
  - Its numbered sections give the eval rule ids `core.N`, `default.N`, and
    `human.N`.
- `SKILL.md`:
  - Frontmatter with `name` matching the directory and a `description` of at
    most 1,024 characters.
  - A `## Iron law` section and a `## Rules` section of at most 10 numbered
    rules.
  - At most 900 words.
- Banned sections: Handoffs, Tripwires, Red Flags, Common Rationalizations.
- Each `references/` file is listed in its SKILL.md with when to read it. It
  sits one level deep and runs at most 1,000 words.
- User-only skills set `disable-model-invocation: true`.
- Don't use `paths:` frontmatter. A skill installed as a directory stays hidden
  until a matching file is opened, which is too late when the first write
  creates that file.

## Changing a rule

1. Edit the source under `agents/.agents/`, then run `make plugin` and
   `make check`.
2. If a rule's number or wording changes, update the eval:
   - Rubric key phrases in `eval/verifier/rubrics/` quote rule text verbatim.
   - `eval/verifier/rules.json` lists every rule id.
   - Run `uv run --project eval eval/scripts/sync_tests.py` to refresh the
     vendored copies.
3. Run the fast eval tier (`make eval-fast`) after editing a skill. Run the
   release tier before a release.
4. Cut a house default that shows no per-rule lift over bare. The
   `houseStyle` suite measures it, and its `follow-the-project` control
   catches a default that overrides a project's own choices.

## The marketing site

`site/` publishes to GitHub Pages when it changes on `main`. Preview it with
`python3 scripts/serve_site.py`. After changing `core.md` or a skill's
frontmatter, run `python3 scripts/build_site_skills.py` to regenerate
`site/skills/index.html`. The tests also check the home page's counts and
every evidence-page figure against `eval/results/`. Keep site changes small
and additive.

## Git

Use topic branches named `feature/`, `fix/`, or `refactor/`. Run `make check`
before each commit.
