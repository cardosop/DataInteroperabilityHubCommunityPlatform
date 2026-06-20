"""TDD tests for scripts/e2e_metrics_diff.py — the PR-comment metrics-diff bot.

The diff bot takes two e2e-metrics JSON files (baseline + current) and emits a
markdown table suitable for posting as a PR comment. Polarity matters:

* Swallowed `except Exception: pass` going *down* is good.
* `page.on('pageerror')` handlers going *up* is good (dual-channel coverage).
* `status_code_assertion_count` is neutral — it's a shape indicator, not a
  quality metric.

Run:
    pytest scripts/tests/test_e2e_metrics_diff.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from e2e_metrics_diff import (
    EMOJI_BAD,
    EMOJI_GOOD,
    EMOJI_NEUTRAL,
    NO_CHANGE,
    _delta_cell,
    render_diff,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "metrics_diff"
BASELINE = FIXTURES / "baseline.json"
MIXED = FIXTURES / "current_mixed_deltas.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "pytest": {
            "except_exception_pass_count": 47,
            "orm_query_count": 1405,
            "status_code_assertion_count": 1310,
            "test_skip_call_count": 251,
        },
        "playwright": {
            "test_skip_true_count": 469,
            "page_on_pageerror_count": 0,
            "page_request_call_count": 33,
            "verify_via_api_call_count": 0,
        },
    }
    for section, items in overrides.items():
        base[section] = {**base.get(section, {}), **items}
    return base


# ----------------------------------------------------------------- _delta_cell


class TestDeltaCell:
    def test_no_change_returns_dash(self):
        assert _delta_cell(10, 10, "down_is_good") == NO_CHANGE
        assert _delta_cell(0, 0, "up_is_good") == NO_CHANGE
        assert _delta_cell(5, 5, "neutral") == NO_CHANGE

    def test_improvement_when_lower_is_better(self):
        cell = _delta_cell(10, 5, "down_is_good")
        assert cell.startswith(EMOJI_GOOD)
        assert "-5" in cell

    def test_regression_when_lower_is_better(self):
        cell = _delta_cell(5, 10, "down_is_good")
        assert cell.startswith(EMOJI_BAD)
        assert "+5" in cell

    def test_improvement_when_higher_is_better(self):
        cell = _delta_cell(0, 28, "up_is_good")
        assert cell.startswith(EMOJI_GOOD)
        assert "+28" in cell

    def test_regression_when_higher_is_better(self):
        cell = _delta_cell(28, 0, "up_is_good")
        assert cell.startswith(EMOJI_BAD)
        assert "-28" in cell

    def test_neutral_always_uses_neutral_emoji(self):
        assert _delta_cell(10, 20, "neutral").startswith(EMOJI_NEUTRAL)
        assert _delta_cell(20, 10, "neutral").startswith(EMOJI_NEUTRAL)


# ----------------------------------------------------------------- render_diff


class TestRenderDiff:
    def test_identical_says_no_changes(self):
        b = _base()
        out = render_diff(b, b)
        assert "## E2E Metrics Delta" in out
        assert "No changes in tracked metrics" in out

    def test_swallow_regression_shows_red(self):
        before = _base()
        after = _base(pytest={"except_exception_pass_count": 50})
        out = render_diff(before, after)
        assert EMOJI_BAD in out
        assert "+3" in out
        assert "`except_exception_pass_count`" in out

    def test_swallow_improvement_shows_green(self):
        before = _base()
        after = _base(pytest={"except_exception_pass_count": 40})
        out = render_diff(before, after)
        assert EMOJI_GOOD in out
        assert "-7" in out

    def test_pageerror_handler_added_is_good(self):
        before = _base()
        after = _base(playwright={"page_on_pageerror_count": 28})
        out = render_diff(before, after)
        # up_is_good metric going up → green
        assert EMOJI_GOOD in out
        assert "+28" in out

    def test_verify_via_api_coverage_growing_is_good(self):
        before = _base()
        after = _base(playwright={"verify_via_api_call_count": 12})
        out = render_diff(before, after)
        assert EMOJI_GOOD in out

    def test_neutral_change_does_not_use_good_or_bad(self):
        before = _base()
        after = _base(pytest={"status_code_assertion_count": 1320})
        out = render_diff(before, after)
        # The row should use the neutral marker; also assert no other row
        # is still flipping emoji for this particular line.
        lines = [ln for ln in out.splitlines() if "`status_code_assertion_count`" in ln]
        assert len(lines) == 1
        assert EMOJI_NEUTRAL in lines[0]
        assert EMOJI_GOOD not in lines[0]
        assert EMOJI_BAD not in lines[0]

    def test_missing_baseline_section_treated_as_zero(self):
        before = {"schema_version": 1}
        after = _base()
        out = render_diff(before, after)
        # Swallows went 0 → 47 → regression (down_is_good metric going up)
        assert EMOJI_BAD in out

    def test_mixed_deltas_end_to_end(self):
        """Fixture file exercises several polarities in one diff."""
        out = render_diff(_load(BASELINE), _load(MIXED))
        assert EMOJI_GOOD in out  # swallows down, pageerror up, verifyViaApi up
        assert EMOJI_BAD in out  # test_skip_call up by 2
        assert EMOJI_NEUTRAL in out  # status_code_assertion_count changed

    def test_output_contains_polarity_legend(self):
        out = render_diff(_base(), _base())
        assert "Polarity legend" in out
        assert EMOJI_GOOD in out and EMOJI_BAD in out and EMOJI_NEUTRAL in out


# ------------------------------------------------------------------------- CLI


class TestCLI:
    def test_cli_writes_markdown_to_stdout(self, tmp_path: Path):
        b = tmp_path / "b.json"
        c = tmp_path / "c.json"
        b.write_text(json.dumps(_base()))
        c.write_text(json.dumps(_base(pytest={"except_exception_pass_count": 45})))

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "e2e_metrics_diff.py"), str(b), str(c)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "## E2E Metrics Delta" in result.stdout
        assert EMOJI_GOOD in result.stdout
        assert "-2" in result.stdout

    def test_cli_wrong_arg_count_returns_2(self, tmp_path: Path):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "e2e_metrics_diff.py"),
                str(tmp_path / "only-one.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2
        assert "usage" in result.stderr.lower()

    def test_cli_missing_file_raises_not_swallowed(self, tmp_path: Path):
        """A missing baseline must raise, not silently render an empty diff."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "e2e_metrics_diff.py"),
                str(tmp_path / "missing.json"),
                str(tmp_path / "also-missing.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
