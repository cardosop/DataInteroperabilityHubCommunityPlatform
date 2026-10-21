"""W8.3 — compliance violation CSV export: formula-injection neutralisation.

The violation ``column`` cell carries dataset column names — strings
that originated in a user-uploaded dataset and can begin with a
spreadsheet formula trigger. Pre-fix, ``iter_violation_csv_bytes``
emitted them verbatim (CWE-1236). These pins run against the REAL
streaming generator (no mocks) and assert the full download is
spreadsheet-safe.
"""

from __future__ import annotations

import csv
import io

from django.test import SimpleTestCase

from hub.apps.compliance.violations_csv import iter_violation_csv_bytes


def _rows(violations) -> list[list[str]]:
    chunks = b"".join(iter_violation_csv_bytes(violations))
    return list(csv.reader(io.StringIO(chunks.decode("utf-8"))))


class ViolationCsvFormulaSafetyTests(SimpleTestCase):
    """Formula-triggering violation fields are neutralised in the export."""

    def test_formula_column_neutralised(self):
        rows = _rows(
            [
                {
                    "column": '=HYPERLINK("http://evil")',
                    "pii_type": "EMAIL",
                    "risk_score": 90,
                    "severity": "HIGH",
                }
            ]
        )
        self.assertEqual(rows[0], ["column", "pii_type", "risk_score", "severity"])
        self.assertEqual(rows[1][0], '\'=HYPERLINK("http://evil")')

    def test_formula_pii_type_and_severity_neutralised(self):
        rows = _rows(
            [
                {"column": "c", "pii_type": "+SUM(1,1)", "risk_score": None, "severity": "-2+3"},
                {"column": "d", "pii_type": "EMAIL", "risk_score": 1, "severity": "@x"},
            ]
        )
        self.assertEqual(rows[1][1], "'+SUM(1,1)")
        self.assertEqual(rows[1][3], "'-2+3")
        self.assertEqual(rows[2][3], "'@x")

    def test_every_cell_is_spreadsheet_safe(self):
        hostile = [
            {"column": "=1+2", "pii_type": "@SUM(1,1)", "risk_score": 50, "severity": "+cmd"},
            {"column": "plain", "pii_type": "EMAIL", "risk_score": 80, "severity": "HIGH"},
        ]
        triggers = ("=", "+", "-", "@", "\t", "\r")
        for row in _rows(hostile)[1:]:
            for cell in row:
                self.assertFalse(
                    cell.startswith(triggers),
                    f"un-neutralised formula cell: {cell!r}",
                )

    def test_risk_score_stays_numeric(self):
        rows = _rows(
            [{"column": "email_col", "pii_type": "EMAIL", "risk_score": 90, "severity": "HIGH"}]
        )
        self.assertEqual(rows[1][2], "90")

    def test_benign_values_roundtrip_unchanged(self):
        violations = [
            {
                "column": "email_col",
                "pii_type": "PII_DIRECT_EMAIL",
                "risk_score": 85,
                "severity": "HIGH",
            },
            {"column": "notes", "pii_type": None, "risk_score": None, "severity": None},
        ]
        rows = _rows(violations)
        self.assertEqual(rows[1], ["email_col", "PII_DIRECT_EMAIL", "85", "HIGH"])
        self.assertEqual(rows[2], ["notes", "", "", ""])

    def test_empty_and_none_input(self):
        self.assertEqual(len(_rows(None)), 1)  # header only
        self.assertEqual(len(_rows([])), 1)
