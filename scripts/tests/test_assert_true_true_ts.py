"""TDD suite for check_assert_true_true.py incl. the Phase T.1 .ts/.tsx
extension.

The Python checker AST-parses ``test_*.py`` under hub/apps; the TS
extension scans frontend test files for TAUTOLOGICAL expectations —
``expect(<X>).toBe(<X>)`` with byte-identical operands (and the
toBeTruthy/toBeFalsy literal forms). A tautological expectation passes
regardless of what the code under test does — the same vacuity class as
``assertTrue(True)``.

No mocks: the real checker functions parse synthetic sources.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_assert_true_true import analyze_file, analyze_ts_source


class TestTypeScriptTautologies:
    def test_identical_literal_operands_are_flagged(self):
        violations = analyze_ts_source("expect(true).toBe(true);")
        assert len(violations) == 1, violations
        assert "tautological" in violations[0][1].lower()

    def test_identical_string_operands_are_flagged(self):
        violations = analyze_ts_source("expect('x').toBe('x');")
        assert len(violations) == 1, violations

    def test_identical_identifier_operands_are_flagged(self):
        violations = analyze_ts_source("expect(selector).toBe(selector);")
        assert len(violations) == 1, violations

    def test_to_equal_with_identical_operands_is_flagged(self):
        violations = analyze_ts_source("expect(1).toEqual(1);")
        assert len(violations) == 1, violations

    def test_literal_truthy_on_true_is_flagged(self):
        violations = analyze_ts_source("expect(true).toBeTruthy();")
        assert len(violations) == 1, violations

    def test_literal_falsy_on_false_is_flagged(self):
        violations = analyze_ts_source("expect(false).toBeFalsy();")
        assert len(violations) == 1, violations

    def test_real_expectation_is_not_flagged(self):
        violations = analyze_ts_source(
            "expect(page.title()).toBe('Dashboard');\n"
            "expect(screen.getByText(/pro/i)).toBeTruthy();\n"
            "expect(1).toBe(2);\n"
        )
        assert violations == [], violations

    def test_multiline_tautology_is_not_flagged_but_documented(self):
        """Line-based regex limitation: a tautology split across lines is
        invisible (documented in the checker docstring). The checker
        remains a GROWTH gate — it over-targets the common single-line
        form rather than mis-reporting."""
        violations = analyze_ts_source("expect(\n  true\n).toBe(\n  true\n);")
        assert violations == [], violations


class TestPythonSideStillWorks:
    def test_assert_true_true_is_flagged(self, tmp_path):
        target = tmp_path / "test_probe.py"
        target.write_text(
            "import unittest\n\n\n"
            "class TestProbe(unittest.TestCase):\n"
            "    def test_stub(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        violations = analyze_file(str(target))
        assert len(violations) == 1, violations

    def test_real_assertion_is_not_flagged(self, tmp_path):
        target = tmp_path / "test_probe.py"
        target.write_text(
            "import unittest\n\n\n"
            "class TestProbe(unittest.TestCase):\n"
            "    def test_real(self):\n"
            "        self.assertEqual(1 + 1, 2)\n",
            encoding="utf-8",
        )
        violations = analyze_file(str(target))
        assert violations == [], violations
