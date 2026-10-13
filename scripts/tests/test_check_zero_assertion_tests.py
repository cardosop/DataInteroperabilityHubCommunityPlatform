"""GATE-39 TDD suite (Phase T.1 / W13) — zero-assertion test checker.

A test function with NO assertion passes vacuously: the function under test
can return None, raise, or regress, and the suite stays green. The paid-tree
vacuity audit (Phase P.9) fixed the known sites by hand; this gate pins the
class with a ratcheted count — the baseline records the current floor and
any NEW assert-free ``test_*`` function fails CI.

No mocks: synthetic modules are parsed by the REAL checker functions.

Documented limitation (pinned by a test below): the analysis is
INTRAPROCEDURAL — a test whose assertions live in a helper counts as
assert-free. That over-counts rather than under-counts, and the gate only
fails on GROWTH, so the limitation can only cause a false FAIL on a
legitimate new helper-asserting test, never a false PASS.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_zero_assertion_tests import (
    analyze_source,
    count_assert_free_tests,
)

# Minimal import shims so the synthetic fixtures are real modules.
_IMPORTS = "import unittest\nimport pytest\nfrom unittest import mock\n\n\n"


def _count(source: str) -> list[str]:
    return analyze_source(_IMPORTS + source)


class TestAssertFreeDetection:
    def test_assert_free_function_is_counted(self):
        names = _count("def test_vacuous():\n    x = 1\n")
        assert "test_vacuous" in names

    def test_bare_pass_body_is_counted(self):
        names = _count("def test_nothing():\n    pass\n")
        assert "test_nothing" in names

    def test_assert_statement_is_an_assertion(self):
        names = _count("def test_real():\n    assert 1 == 1\n")
        assert names == [], names

    def test_self_assert_method_is_an_assertion(self):
        names = _count(
            "class TestThing(unittest.TestCase):\n"
            "    def test_real(self):\n"
            "        self.assertEqual(1, 1)\n"
        )
        assert names == [], names

    def test_self_fail_is_an_assertion(self):
        names = _count(
            "class TestThing(unittest.TestCase):\n"
            "    def test_fails(self):\n"
            "        self.fail('nope')\n"
        )
        assert names == [], names

    def test_pytest_raises_counts_as_an_assertion(self):
        names = _count(
            "def test_raises():\n"
            "    with pytest.raises(ValueError, match='boom'):\n"
            "        raise ValueError('boom')\n"
        )
        assert names == [], names

    def test_pytest_fail_counts_as_an_assertion(self):
        names = _count("def test_fails():\n    pytest.fail('nope')\n")
        assert names == [], names

    def test_mock_assertion_calls_are_assertions(self):
        names = _count(
            "def test_mock(m):\n"
            "    m.run(1)\n"
            "    m.run.assert_called_once_with(1)\n"
            "    m.other.assert_not_called()\n"
        )
        assert names == [], names

    def test_helper_based_assertion_is_counted(self):
        """The documented intraprocedural limitation: a test that asserts
        only via a helper counts as assert-free (conservative over-count)."""
        names = _count("def test_via_helper(self):\n    self._check()\n")
        assert "test_via_helper" in names

    def test_plain_call_is_not_an_assertion(self):
        names = _count("def test_side_effect_only():\n    build_something()\n")
        assert "test_side_effect_only" in names


class TestDirectoryScan:
    def test_count_assert_free_tests_across_a_tree(self, tmp_path):
        app = tmp_path / "app" / "tests"
        app.mkdir(parents=True)
        (app / "test_a.py").write_text(
            _IMPORTS + "def test_real():\n    assert 1 == 1\ndef test_vacuous():\n    pass\n",
            encoding="utf-8",
        )
        (app / "test_b.py").write_text(
            _IMPORTS + "def test_also_vacuous():\n    x = 2\n",
            encoding="utf-8",
        )
        (app / "not_a_test.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        (app / "migrations").mkdir()
        (app / "migrations" / "test_migration.py").write_text(
            "def test_skip():\n    pass\n", encoding="utf-8"
        )
        names = count_assert_free_tests([str(tmp_path)])
        offenders = {n.split(":")[-1] for n in names}
        assert offenders == {"test_vacuous", "test_also_vacuous"}, names
