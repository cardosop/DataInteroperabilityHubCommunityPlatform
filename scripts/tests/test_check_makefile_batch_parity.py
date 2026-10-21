"""TDD pins for ``check_makefile_batch_parity.py`` — the GATE-43 batch-coverage guard.

Rules pinned (all fixture-driven, no mocks — the parser/coverage functions
run on synthetic Makefile text; the integration pin runs the real checker
against the real tree):

- ``parse_makefile`` attaches recipe lines to the right targets and ignores
  comments/directives;
- ``invoked_targets`` reads both ``$(MAKE)`` and ``${MAKE}`` calls;
- ``is_fanout`` is true only for recipes made exclusively of MAKE lines
  (umbrellas), not for mixed recipes or empty ones;
- coverage: a leaf batch target not invoked by ``test-batch-all`` (directly
  or transitively) is a violation; a fan-out umbrella whose children are
  all covered is NOT a violation;
- exclusions: a listed-but-undefined target is a violation (stale entry);
- parity note: the block must state the exact derived numbers — jobs,
  reusable workflows, CI-parity targets, batch targets; a missing or
  malformed block is a violation;
- the REAL repo passes its own gate (self-audit — the ratchet that would
  have caught the task-0.2 omission: 6-7…6-21, 7-7…7-12, 12-1…12-3).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_makefile_batch_parity import (
    batch_coverage_violations,
    invoked_targets,
    is_fanout,
    makefile_target_counts,
    parity_comment_violations,
    parse_makefile,
)

# ── Fixtures ──────────────────────────────────────────────────────────

PARITY_NOTE = """# ── CI-Makefile parity note ──────────────────────────────────────────
# CI has {jobs} jobs (ci.yml + e2e.yml + {reusable} reusable workflows). The Makefile
# provides {parity} CI-parity targets + {batch} batch targets. Remaining CI jobs
# are CI-only by design.
"""

BASE = (
    PARITY_NOTE.format(jobs=3, reusable=1, parity=2, batch=3)
    + """
# ── Target naming convention ─────────────────────────────────────────

test-ci-lint:
	-ruff check .

test-batch-a:
	-$(MAKE) test-batch-a-1
	-$(MAKE) test-batch-a-2

test-batch-a-1:
	@echo a1

test-batch-a-2:
	@echo a2

test-batch-all:
	-$(MAKE) test-batch-a
"""
)


def makefile(*extra_targets: str) -> str:
    """BASE plus extra target definitions (recipe lines included verbatim)."""
    return BASE + "\n".join(extra_targets) + "\n"


# ── Parsing ───────────────────────────────────────────────────────────


def test_parse_makefile_attaches_recipe_lines():
    targets = parse_makefile(BASE)
    assert targets["test-batch-a-1"] == ["\t@echo a1"]
    assert targets["test-batch-a-2"] == ["\t@echo a2"]
    assert len(targets["test-batch-all"]) == 1


def test_parse_makefile_ignores_comments_and_directives():
    text = (
        BASE
        + """
# a comment line

export PATH := $(CURDIR)/venv/bin:$(PATH)

help: ## help target
	@echo help
"""
    )
    targets = parse_makefile(text)
    assert "export" not in targets
    assert "# a comment line" not in targets


def test_invoked_targets_reads_dollar_and_brace_make():
    recipes = [
        "\t-$(MAKE) test-batch-a-1 TEST_DB=$(TEST_DB)",
        "\t@${MAKE} test-batch-a-2",
        "\tdocker compose exec -T api python -m pytest",  # no MAKE call
    ]
    assert invoked_targets(recipes) == {"test-batch-a-1", "test-batch-a-2"}


def test_is_fanout_true_only_for_pure_make_recipes():
    assert is_fanout(["\t-$(MAKE) a", "\t@${MAKE} b"])
    assert not is_fanout(["\t-$(MAKE) a", "\t@echo setup"])
    assert not is_fanout([])


# ── Coverage ──────────────────────────────────────────────────────────


def test_coverage_clean_when_all_leaves_reachable_via_umbrella():
    assert batch_coverage_violations(BASE, excluded={}) == []


def test_coverage_flags_leaf_missing_from_test_batch_all():
    text = makefile(
        "test-batch-a-3:",
        "\t@echo a3",
    )
    assert batch_coverage_violations(text, excluded={}) == [
        "test-batch-a-3: defined but not reachable from test-batch-all "
        "(not invoked by test-batch-all and not a covered fan-out umbrella)"
    ]


def test_coverage_accepts_fanout_umbrella_whose_children_are_covered():
    # test-batch-a is not itself invoked by test-batch-all in this fixture —
    # its children are; the umbrella must still count as covered.
    text = BASE.replace(
        "\t-$(MAKE) test-batch-a\n", "\t-$(MAKE) test-batch-a-1\n\t-$(MAKE) test-batch-a-2\n"
    )
    assert batch_coverage_violations(text, excluded={}) == []


def test_coverage_flags_umbrella_with_an_uncovered_child():
    # test-batch-a (umbrella) itself invokes a-3 — so BOTH the leaf and
    # the umbrella whose child it is must be flagged.
    text = (
        BASE.replace(
            "\t-$(MAKE) test-batch-a\n",
            "\t-$(MAKE) test-batch-a-1\n\t-$(MAKE) test-batch-a-2\n",
        ).replace(
            # scope to the umbrella's OWN recipe block — the same line
            # pattern also exists in test-batch-all's recipe
            "test-batch-a:\n\t-$(MAKE) test-batch-a-1\n\t-$(MAKE) test-batch-a-2\n",
            "test-batch-a:\n\t-$(MAKE) test-batch-a-1\n\t-$(MAKE) test-batch-a-2\n\t-$(MAKE) test-batch-a-3\n",
        )
        + "test-batch-a-3:\n\t@echo a3\n"
    )
    violations = batch_coverage_violations(text, excluded={})
    # sorted order: the umbrella (test-batch-a) first, then the leaf
    assert violations == [
        "test-batch-a: defined but not reachable from test-batch-all "
        "(not invoked by test-batch-all and not a covered fan-out umbrella)",
        "test-batch-a-3: defined but not reachable from test-batch-all "
        "(not invoked by test-batch-all and not a covered fan-out umbrella)",
    ]


def test_coverage_flags_stale_exclusion_entry():
    text = makefile()
    violations = batch_coverage_violations(text, excluded={"test-batch-zzz": "never existed"})
    assert violations == [
        "test-batch-zzz: listed in EXCLUDED_FROM_BATCH_ALL but not defined in Makefile"
    ]


# ── Parity comment ────────────────────────────────────────────────────


def test_parity_comment_accepts_derived_numbers():
    assert parity_comment_violations(BASE, jobs=3, reusable=1, batch=3, parity=2) == []


def test_parity_comment_flags_each_mismatched_number():
    violations = parity_comment_violations(BASE, jobs=4, reusable=2, batch=5, parity=1)
    assert "parity note: states 3 CI jobs; derived 4" in violations
    assert "parity note: states 1 reusable workflows; derived 2" in violations
    assert "parity note: states 2 CI-parity targets; derived 1" in violations
    assert "parity note: states 3 batch targets; derived 5" in violations


def test_parity_comment_flags_missing_block():
    text = "test-ci-lint:\n\t-ruff check .\n"
    assert parity_comment_violations(text, 1, 0, 0, 1) == [
        "CI-Makefile parity note comment block missing or malformed"
    ]


# ── Self-audit (the ratchet) ──────────────────────────────────────────


def test_real_makefile_passes_its_own_gate():
    import check_makefile_batch_parity as checker

    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    jobs, reusable = checker.ci_job_counts()
    batch, parity = makefile_target_counts(text)
    # default exclusions — this pin audits the REAL allowlist too
    violations = batch_coverage_violations(text) + parity_comment_violations(
        text, jobs, reusable, batch, parity
    )
    assert violations == [], "GATE-43 self-audit violations:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


def test_batch_target_count_matches_definitions():
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    batch, parity = makefile_target_counts(text)
    assert batch == 151  # every test-batch-* definition minus test-batch-all
    assert parity == 4  # test-ci umbrella + test-ci-lint/backend/frontend
