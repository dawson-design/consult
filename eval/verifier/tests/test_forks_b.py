"""Both sides of three forks-suite tasks: config-or-constant, special-case-or-reshape, copy-or-home.

  python3 -m unittest discover eval/verifier/tests

Each task ships its oracle (solution/files/, the simpler side) and the other
side (solution/other-side/) as overlays on the starting repository. Both must
pass the hidden check; the rule probe must score the oracle 1 and the other
side 0. More variants pin what each probe counts as which side. Scripts run
the way consult_lib runs them: passed to `node --input-type=module -e` with
the workspace as the working directory. Needs Node 22 or later on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
TASKS = EVAL_DIR / "tasks"
HIDDEN = EVAL_DIR / "verifier" / "hidden"

# (path, old, new) replacements applied after the overlay.
Edit = tuple[str, str, str]


class ForkCase(unittest.TestCase):
    task = ""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._count = 0

    def workspace(self, overlay: str | None, *edits: Edit, files: dict[str, str] | None = None) -> Path:
        self._count += 1
        root = Path(self._tmp.name) / f"w{self._count}"
        shutil.copytree(TASKS / self.task / "environment" / "workspace", root)
        if overlay:
            shutil.copytree(TASKS / self.task / "solution" / overlay, root, dirs_exist_ok=True)
        for path, old, new in edits:
            text = (root / path).read_text()
            self.assertIn(old, text, f"edit does not apply to {path}")
            (root / path).write_text(text.replace(old, new))
        for path, text in (files or {}).items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text)
        return root

    def node(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["node", *args], cwd=root, capture_output=True, text=True, timeout=120, check=False)

    def hidden_passes(self, root: Path) -> bool:
        script = (HIDDEN / f"{self.task}.mjs").read_text()
        return self.node(root, "--input-type=module", "-e", script).returncode == 0

    def fork_score(self, root: Path) -> int:
        script = (HIDDEN / f"{self.task}.rules.mjs").read_text()
        result = self.node(root, "--input-type=module", "-e", script)
        lines = [line for line in result.stdout.strip().splitlines() if line.startswith("{")]
        self.assertTrue(lines, f"probe printed no result:\n{result.stderr[-1500:]}")
        scores = json.loads(lines[-1])
        rule = f"fork.{self.task.removeprefix('fork-')}"
        self.assertEqual(list(scores), [rule])
        return scores[rule]

    def assertSide(self, root: Path, score: int) -> None:
        self.assertTrue(self.hidden_passes(root), "the hidden check rejected a working tree")
        self.assertEqual(self.fork_score(root), score)

    def check_both_sides(self) -> None:
        oracle = self.workspace("files")
        self.assertSide(oracle, 1)
        self.assertEqual(self.node(oracle, "--test").returncode, 0, "the oracle's own tests fail")
        self.assertSide(self.workspace("other-side"), 0)
        start = self.workspace(None)
        self.assertFalse(self.hidden_passes(start), "the hidden check passed the starting repository")
        self.assertEqual(self.fork_score(start), 0, "an idle agent took neither side")


class ConfigOrConstantTests(ForkCase):
    task = "fork-config-or-constant"
    PAYOUTS = "src/payouts.js"
    CONSTANT = "const PLATFORM_FEE_RATE = 0.029;"

    def test_the_constant_scores_1_and_the_environment_variable_0(self) -> None:
        self.check_both_sides()

    def test_a_parameter_defaulting_to_the_constant_is_still_a_constant(self) -> None:
        root = self.workspace(
            "files",
            (
                self.PAYOUTS,
                "export function payoutFor(order) {",
                "export function payoutFor(order, feeRate = PLATFORM_FEE_RATE) {",
            ),
            (self.PAYOUTS, "grossCents * PLATFORM_FEE_RATE", "grossCents * feeRate"),
        )
        self.assertSide(root, 1)

    def test_a_config_file_holding_the_rate_is_the_other_side(self) -> None:
        root = self.workspace(
            "files",
            (
                self.PAYOUTS,
                self.CONSTANT,
                'import fees from "../config/fees.json" with { type: "json" };\nconst PLATFORM_FEE_RATE = fees.platformFeeRate;',
            ),
            files={"config/fees.json": '{ "platformFeeRate": 0.029 }\n'},
        )
        self.assertSide(root, 0)

    def test_an_environment_read_the_text_scan_misses_is_seen_at_runtime(self) -> None:
        root = self.workspace(
            "files",
            (self.PAYOUTS, self.CONSTANT, 'import { feeRate as PLATFORM_FEE_RATE } from "./settings.js";'),
            files={
                "src/settings.js": "const { env } = process;\nexport const feeRate = Number(env.FEE_RATE ?? 0.029);\n"
            },
        )
        self.assertSide(root, 0)

    def test_a_command_line_flag_is_the_other_side(self) -> None:
        cli = (
            'import { parseArgs } from "node:util";\n'
            'import { payoutsBySeller } from "../src/payouts.js";\n'
            'const { values } = parseArgs({ options: { "fee-rate": { type: "string" } } });\n'
            "console.log(values, payoutsBySeller([]));\n"
        )
        self.assertSide(self.workspace("files", files={"bin/payouts.js": cli}), 0)

    def test_a_comment_naming_the_environment_is_not_a_read(self) -> None:
        root = self.workspace(
            "files",
            (self.PAYOUTS, self.CONSTANT, f"// Not read from process.env: a code change sets it.\n{self.CONSTANT}"),
        )
        self.assertSide(root, 1)


class SpecialCaseOrReshapeTests(ForkCase):
    task = "fork-special-case-or-reshape"
    RECEIPT = (
        "export function receiptLine(p, a) {\n"
        "  return `Charged $${(a / 100).toFixed(2)} to ${describePayment(p)}`;\n"
        "}\n"
    )
    CARD_OK = (
        "const [y, m] = today.split('-').map(Number); return p.expYear > y || (p.expYear === y && p.expMonth >= m);"
    )

    def variant(self, source: str) -> Path:
        return self.workspace(None, files={"src/payments.js": source + self.RECEIPT})

    def test_one_dispatch_point_scores_1_and_a_bank_check_per_function_0(self) -> None:
        self.check_both_sides()

    def test_a_switch_on_the_method_in_each_function_is_the_other_side(self) -> None:
        source = (
            "export function describePayment(p) {\n"
            "  switch (p.method) {\n"
            "    case 'bank_transfer': return `${p.bankName} account ending ${p.accountLast4}`;\n"
            "    default: return `${p.cardBrand} ending ${p.cardLast4}`;\n"
            "  }\n"
            "}\n"
            "export function isChargeable(p, today) {\n"
            "  switch (p.method) {\n"
            "    case 'bank_transfer': return true;\n"
            f"    default: {{ {self.CARD_OK} }}\n"
            "  }\n"
            "}\n"
            "export function processingFeeCents(p, a) {\n"
            "  switch (p.method) {\n"
            "    case 'bank_transfer': return Math.min(Math.round(a * 0.008), 500);\n"
            "    default: return Math.round(a * 0.029) + 30;\n"
            "  }\n"
            "}\n"
        )
        self.assertSide(self.variant(source), 0)

    def test_a_ternary_flag_in_each_function_is_the_other_side(self) -> None:
        source = (
            "const bank = (p) => p.method === 'bank_transfer';\n"
            "export const describePayment = (p) =>\n"
            "  bank(p) ? `${p.bankName} account ending ${p.accountLast4}` : `${p.cardBrand} ending ${p.cardLast4}`;\n"
            "export function isChargeable(p, today) {\n"
            "  const [y, m] = today.split('-').map(Number);\n"
            "  return bank(p) || p.expYear > y || (p.expYear === y && p.expMonth >= m);\n"
            "}\n"
            "export const processingFeeCents = (p, a) =>\n"
            "  bank(p) ? Math.min(Math.round(a * 0.008), 500) : Math.round(a * 0.029) + 30;\n"
        )
        self.assertSide(self.variant(source), 0)

    def test_one_normalizing_function_with_a_switch_is_one_dispatch_point(self) -> None:
        source = (
            "function view(p) {\n"
            "  switch (p.method) {\n"
            "    case 'bank_transfer':\n"
            "      return { label: `${p.bankName} account ending ${p.accountLast4}`, chargeable: () => true,\n"
            "        fee: (a) => Math.min(Math.round(a * 0.008), 500) };\n"
            "    case 'card':\n"
            "      return { label: `${p.cardBrand} ending ${p.cardLast4}`,\n"
            f"        chargeable: (today) => {{ {self.CARD_OK} }}, fee: (a) => Math.round(a * 0.029) + 30 }};\n"
            "    default:\n"
            "      throw new RangeError(`unknown payment method: ${p.method}`);\n"
            "  }\n"
            "}\n"
            "export const describePayment = (p) => view(p).label;\n"
            "export const isChargeable = (p, today) => view(p).chargeable(today);\n"
            "export const processingFeeCents = (p, a) => view(p).fee(a);\n"
        )
        self.assertSide(self.variant(source), 1)

    def test_a_lookup_indexed_in_each_function_has_no_branch_to_count(self) -> None:
        root = self.workspace(
            "files",
            (
                "src/payments.js",
                "return methodOf(payment).describe(payment);",
                "return METHODS[payment.method].describe(payment);",
            ),
            (
                "src/payments.js",
                "return methodOf(payment).feeCents(amountCents);",
                "return METHODS[payment.method].feeCents(amountCents);",
            ),
        )
        self.assertSide(root, 1)

    def test_wrong_bank_answers_take_neither_side(self) -> None:
        root = self.workspace(
            "files", ("src/payments.js", "Math.round(amountCents * 0.008)", "Math.round(amountCents * 0.009)")
        )
        self.assertFalse(self.hidden_passes(root))
        self.assertEqual(self.fork_score(root), 0)


class CopyOrHomeTests(ForkCase):
    task = "fork-copy-or-home"
    HOLIDAYS = 'const HOLIDAYS = new Set(["2026-01-01", "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]);'

    def test_calling_the_home_scores_1_and_a_second_copy_0(self) -> None:
        self.check_both_sides()

    def test_a_rule_moved_to_its_own_module_and_called_from_both_is_one_home(self) -> None:
        delivery = (TASKS / self.task / "solution" / "files" / "src" / "delivery.js").read_text()
        data = delivery[delivery.index("// The warehouse") : delivery.index("const TRANSIT_DAYS")]
        functions = delivery[delivery.index("function nextDay") : delivery.index("export function estimateDelivery")]
        calendar = data + functions
        rest = delivery.replace(data, 'import { addBusinessDays } from "./calendar.js";\n\n').replace(functions, "")
        root = self.workspace(
            "files",
            ("src/tickets.js", 'from "./delivery.js"', 'from "./calendar.js"'),
            files={"src/calendar.js": calendar, "src/delivery.js": rest},
        )
        self.assertSide(root, 1)

    def test_reusing_the_holidays_but_rewriting_the_weekend_is_a_copy(self) -> None:
        root = self.workspace(
            "other-side",
            ("src/delivery.js", "const HOLIDAYS", "export const HOLIDAYS"),
            (
                "src/tickets.js",
                self.HOLIDAYS.replace("const HOLIDAYS", "const SUPPORT_HOLIDAYS"),
                'import { HOLIDAYS as SUPPORT_HOLIDAYS } from "./delivery.js";',
            ),
        )
        self.assertSide(root, 0)

    def test_a_copy_that_reuses_the_weekend_literal_is_held_twice(self) -> None:
        root = self.workspace(
            "other-side",
            ("src/tickets.js", "weekday !== 0 && weekday !== 6", "!new Set([0, 6]).has(weekday)"),
        )
        self.assertSide(root, 0)


if __name__ == "__main__":
    unittest.main()
