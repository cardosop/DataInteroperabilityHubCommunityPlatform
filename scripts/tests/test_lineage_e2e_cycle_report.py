"""
Phase 228 (228.0.DoD.6) — E2E cycle-report aggregator tests.

The aggregator script powers the DoD.6 gate ("strict-count assertion
green for ≥7 staging cycles"). Tests are pure-Python — no Django
needed because the aggregator reads JSONL files, not the database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# Make the script importable.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import lineage_e2e_cycle_report as cyc  # noqa: E402


# ---------------------------------------------------------------------------
# compute_consecutive_green_streak
# ---------------------------------------------------------------------------


def _green(cycle_id: str = "x") -> dict:
    return {
        "cycle_id": cycle_id,
        "timestamp": "2026-04-30T00:00:00Z",
        "lineage_strict_content_status": "passed",
        "lineage_empty_state_status": "passed",
    }


def _failed(cycle_id: str = "x") -> dict:
    return {
        "cycle_id": cycle_id,
        "timestamp": "2026-04-30T00:00:00Z",
        "lineage_strict_content_status": "failed",
        "lineage_empty_state_status": "passed",
    }


def _skipped(cycle_id: str = "x") -> dict:
    return {
        "cycle_id": cycle_id,
        "timestamp": "2026-04-30T00:00:00Z",
        "lineage_strict_content_status": "skipped",
        "lineage_empty_state_status": "passed",
    }


def test_empty_history_returns_zero():
    assert cyc.compute_consecutive_green_streak([]) == 0


def test_all_green_returns_count():
    assert cyc.compute_consecutive_green_streak([_green(), _green(), _green()]) == 3


def test_streak_breaks_at_most_recent_failure():
    """A non-green most-recent cycle resets the streak even if
    every earlier cycle was green. The DoD requires CONSECUTIVE green."""
    history = [_green(), _green(), _green(), _failed()]
    assert cyc.compute_consecutive_green_streak(history) == 0


def test_streak_counts_only_consecutive_tail():
    """7 green at the start, 1 failure, then 2 more green → tail is 2."""
    history = [_green()] * 7 + [_failed()] + [_green(), _green()]
    assert cyc.compute_consecutive_green_streak(history) == 2


def test_skipped_breaks_streak():
    """A skip is NOT a pass — the strict-content assertion must
    actually run and pass for DoD.6 to be satisfied."""
    history = [_green(), _green(), _skipped(), _green()]
    assert cyc.compute_consecutive_green_streak(history) == 1


def test_streak_requires_both_specs_green():
    """Both the strict-content spec AND the empty-state spec must
    pass per cycle. A failure in either breaks the streak."""
    cycle = {
        "cycle_id": "x",
        "timestamp": "x",
        "lineage_strict_content_status": "passed",
        "lineage_empty_state_status": "failed",  # broken
    }
    assert cyc.compute_consecutive_green_streak([cycle]) == 0


# ---------------------------------------------------------------------------
# CLI integration — append + report cycle
# ---------------------------------------------------------------------------


def test_append_then_report_round_trip(tmp_path: Path):
    """Append 7 green cycles → report --threshold=7 returns 0."""
    history_file = tmp_path / "cycles.jsonl"

    for i in range(7):
        rc = cyc.main([
            "append",
            f"--history-file={history_file}",
            f"--cycle-id=staging-cycle-{i}",
            "--strict-status=passed",
            "--empty-status=passed",
        ])
        assert rc == 0

    # Report should pass.
    rc = cyc.main(["report", f"--history-file={history_file}", "--threshold=7"])
    assert rc == 0


def test_report_below_threshold_returns_one(tmp_path: Path):
    history_file = tmp_path / "cycles.jsonl"
    # Only 3 cycles; threshold=7 → INSUFFICIENT.
    for i in range(3):
        cyc.main([
            "append",
            f"--history-file={history_file}",
            f"--cycle-id=staging-cycle-{i}",
            "--strict-status=passed",
            "--empty-status=passed",
        ])
    rc = cyc.main(["report", f"--history-file={history_file}", "--threshold=7"])
    assert rc == 1


def test_report_malformed_json_returns_two(tmp_path: Path):
    """Malformed JSONL → exit 2 (CI gate fails fast)."""
    history_file = tmp_path / "cycles.jsonl"
    history_file.write_text("not-valid-json\n", encoding="utf-8")
    rc = cyc.main(["report", f"--history-file={history_file}", "--threshold=7"])
    assert rc == 2


def test_report_includes_canonical_keys_in_stdout(tmp_path: Path, capsys):
    history_file = tmp_path / "cycles.jsonl"
    cyc.main([
        "append",
        f"--history-file={history_file}",
        "--cycle-id=staging-cycle-1",
        "--strict-status=passed",
        "--empty-status=passed",
    ])
    cyc.main(["report", f"--history-file={history_file}", "--threshold=1"])
    captured = capsys.readouterr()
    # The last line of stdout is the JSON report.
    json_line = [ln for ln in captured.out.strip().splitlines() if ln.startswith("{")][-1]
    report = json.loads(json_line)
    for key in (
        "phase", "history_file", "total_cycles", "consecutive_green_streak",
        "threshold", "status", "last_cycle_id", "checked_at",
    ):
        assert key in report, f"missing canonical key {key!r}; got {report!r}"
