"""W8.3 — output-safety primitives (CSV formula-injection neutralisation).

Pins the shared ``csv_formula_safe`` contract used by every
application-generated CSV export (audit, compliance, RoPA, impact).

Scope note (recorded decision): raw-data exports (dataset downloads,
warehouse staging files) are deliberately NOT routed through this
helper — those bytes are the customer's data and mutating them would
corrupt fidelity. The helper is for application-generated *report*
cells, where each cell is a displayed attribute and the consumer is a
spreadsheet application.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from hub.apps.core.utils.output_safety import (
    CSV_FORMULA_TRIGGERS,
    csv_formula_safe,
)


class CsvFormulaSafeTests(SimpleTestCase):
    """``csv_formula_safe`` neutralises spreadsheet formula triggers."""

    def test_equals_prefix_neutralised(self):
        self.assertEqual(csv_formula_safe("=1+2"), "'=1+2")
        self.assertEqual(
            csv_formula_safe('=HYPERLINK("http://evil")'), '\'=HYPERLINK("http://evil")'
        )
        self.assertEqual(csv_formula_safe("="), "'=")

    def test_plus_prefix_neutralised(self):
        self.assertEqual(csv_formula_safe("+SUM(1,1)"), "'+SUM(1,1)")
        self.assertEqual(csv_formula_safe("+"), "'+")

    def test_minus_prefix_neutralised(self):
        self.assertEqual(csv_formula_safe("-2+3+cmd|' /C calc'!A0"), "'-2+3+cmd|' /C calc'!A0")
        self.assertEqual(csv_formula_safe("-"), "'-")

    def test_at_prefix_neutralised(self):
        self.assertEqual(csv_formula_safe("@SUM(1,1)"), "'@SUM(1,1)")
        self.assertEqual(csv_formula_safe("@"), "'@")

    def test_tab_and_carriage_return_prefixes_neutralised(self):
        self.assertEqual(csv_formula_safe("\t=1+2"), "'\t=1+2")
        self.assertEqual(csv_formula_safe("\r=1+2"), "'\r=1+2")

    def test_benign_strings_pass_through_unchanged(self):
        cases = [
            "",
            "customer-db",
            "Acme Corp",
            "name = 1+2",  # trigger char not at position 0
            "  =1+2",  # leading whitespace: spreadsheet apps treat as text
            "O'Brien & Sons",
            "café — 日本語",
            "https://example.com",
            "50%",
        ]
        for value in cases:
            self.assertEqual(csv_formula_safe(value), value, f"mutated benign value: {value!r}")

    def test_numbers_booleans_and_none_pass_through(self):
        # Numeric columns must stay numeric — guarding them would turn
        # them into text and corrupt spreadsheet formulas/aggregations.
        self.assertEqual(csv_formula_safe(42), 42)
        self.assertEqual(csv_formula_safe(3.14), 3.14)
        self.assertEqual(csv_formula_safe(-5), -5)
        self.assertEqual(csv_formula_safe(True), True)
        self.assertEqual(csv_formula_safe(False), False)
        self.assertIsNone(csv_formula_safe(None))

    def test_non_string_containers_pass_through(self):
        payload = ["=1+2", {"a": 1}]
        self.assertIs(csv_formula_safe(payload), payload)

    def test_trigger_set_is_the_documented_owasp_list(self):
        self.assertEqual(CSV_FORMULA_TRIGGERS, ("=", "+", "-", "@", "\t", "\r"))
