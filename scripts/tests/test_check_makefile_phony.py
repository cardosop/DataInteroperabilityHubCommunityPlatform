"""TDD pins for ``check_makefile_phony.py`` — the Makefile ``.PHONY``
completeness gate (close-test-coverage-gaps 0.1).

The gate exists because a non-phony target silently stops running when a
file or directory with its name appears next to the Makefile — and batch
targets drifted out of ``.PHONY`` for months (``test-batch-6-7``…``6-21``,
``7-7``…``7-12``, ``8-4``…``8-7``, ``staging-*``). Every parse decision is
drilled both ways against minimal makefile fixtures (no mocks — real text
through the real parser), plus a drift pin against the repository's live
Makefile so a future target added without a ``.PHONY`` entry fails here.

RED drills: each fixture asserts exactly which names the parser sees, so a
loosened parser (or one that skips real targets) fails the suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_makefile_phony as gate  # type: ignore[import-not-found]  # runtime sys.path injection, scripts/ is not a package

MAKEFILE = gate.MAKEFILE
parse_targets = gate.parse_targets
parse_phony = gate.parse_phony
find_missing = gate.find_missing


class TestParseTargets:
    def test_single_target_rule(self):
        targets = parse_targets("build: deps\n\t@echo built\n")
        assert targets == {"build"}

    def test_target_without_prereqs(self):
        assert parse_targets("clean:\n") == {"clean"}

    def test_multi_target_rule_contributes_every_name(self):
        assert parse_targets("a b c: dep\n") == {"a", "b", "c"}

    def test_recipe_lines_are_not_targets(self):
        targets = parse_targets("build:\n\tpython -m pytest tests/ -q\n")
        assert targets == {"build"}

    def test_variable_assignments_are_not_targets(self):
        text = (
            "VAR := value\n"
            "PLAIN = value\n"
            "OPT ?= value\n"
            "ADD += value\n"
            "SHELL_EVAL != command\n"
            "real: \n"
        )
        assert parse_targets(text) == {"real"}

    def test_directive_lines_are_not_targets_but_conditional_rules_are(self):
        # The directive LINES themselves are not targets, but rules INSIDE
        # a conditional block are real rules for the configuration where
        # the condition holds — skipping them would leave exactly the
        # non-phony target the gate exists to catch.
        text = (
            "ifeq ($(X),1)\n"
            "only-here:\n"
            "endif\n"
            "ifdef FOO\n"
            "also-here:\n"
            "endif\n"
            "include other.mk\n"
            "define VAR\n"
            "text\n"
            "endef\n"
            "export X = 1\n"
            "vpath %.py src\n"
            "real:\n"
        )
        assert parse_targets(text) == {"only-here", "also-here", "real"}

    def test_pattern_rules_are_skipped(self):
        assert parse_targets("%.o: %.c\n") == set()

    def test_special_targets_are_skipped(self):
        text = ".PHONY: clean\n.DEFAULT_GOAL := all\n.SUFFIXES: .c .o\nreal:\n"
        assert parse_targets(text) == {"real"}


class TestParsePhony:
    def test_collects_every_phony_line(self):
        text = ".PHONY: a b\n.PHONY: c\n"
        assert parse_phony(text) == {"a", "b", "c"}

    def test_phony_mentions_are_not_targets(self):
        # A name that appears ONLY in .PHONY is not a declared target.
        text = ".PHONY: ghost\nreal:\n"
        assert parse_targets(text) == {"real"}


class TestFindMissing:
    def test_missing_targets_are_reported_sorted(self):
        text = ".PHONY: alpha\nalpha:\nzed:\nmid:\n"
        _, _, missing = find_missing(text)
        assert missing == ["mid", "zed"]

    def test_complete_makefile_reports_nothing(self):
        text = ".PHONY: a b c\na: \nb: x\nc a: dep\n"
        targets, _phony, missing = find_missing(text)
        assert targets == {"a", "b", "c"}
        assert missing == []

    def test_regression_the_original_drift_shape(self):
        # The exact drift that motivated the gate: batch targets declared
        # but absent from the .PHONY line.
        text = (
            ".PHONY: test-batch-6-1 test-batch-6-2\n"
            "test-batch-6-1:\n"
            "test-batch-6-2:\n"
            "test-batch-6-3:\n"
        )
        _, _, missing = find_missing(text)
        assert missing == ["test-batch-6-3"]


class TestLiveMakefile:
    def test_the_repository_makefile_is_complete(self):
        # Drift pin: adding a target without a .PHONY entry must fail here.
        text = MAKEFILE.read_text()
        targets, _phony, missing = find_missing(text)
        assert targets, "the live Makefile must declare targets"
        assert missing == [], f".PHONY is missing: {missing}"
