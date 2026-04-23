"""TDD tests for scripts/check_skip_counter.py + tests/e2e/_guards/_skip_counter.py.

Run (stdlib-only; ignores project pytest.ini to stay isolated):
    pytest -c /dev/null scripts/tests/test_check_skip_counter.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT))

from check_skip_counter import (  # noqa: E402
    aggregate_skip_events,
    check_thresholds,
    main,
)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for e in entries:
            fp.write(json.dumps(e) + "\n")


class TestAggregate:
    def test_empty_dir_returns_empty_counter(self, tmp_path: Path):
        assert aggregate_skip_events(tmp_path) == {}

    def test_missing_dir_returns_empty_counter(self, tmp_path: Path):
        assert aggregate_skip_events(tmp_path / "nonexistent") == {}

    def test_single_file_counts_by_reason(self, tmp_path: Path):
        _write_jsonl(
            tmp_path / "skip-events.jsonl",
            [
                {"test": "t1", "reason": "S3 not reachable"},
                {"test": "t2", "reason": "S3 not reachable"},
                {"test": "t3", "reason": "Semantic service not importable"},
            ],
        )
        counter = aggregate_skip_events(tmp_path)
        assert counter["S3 not reachable"] == 2
        assert counter["Semantic service not importable"] == 1

    def test_multiple_worker_files_aggregate(self, tmp_path: Path):
        _write_jsonl(
            tmp_path / "worker1" / "skip-events.jsonl",
            [{"test": "t1", "reason": "S3 not reachable"}],
        )
        _write_jsonl(
            tmp_path / "worker2" / "skip-events.jsonl",
            [{"test": "t2", "reason": "S3 not reachable"}],
        )
        counter = aggregate_skip_events(tmp_path)
        assert counter["S3 not reachable"] == 2

    def test_blank_lines_are_ignored(self, tmp_path: Path):
        path = tmp_path / "skip-events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"test":"t1","reason":"x"}\n\n   \n{"test":"t2","reason":"x"}\n'
        )
        assert aggregate_skip_events(tmp_path) == {"x": 2}

    def test_malformed_jsonl_raises(self, tmp_path: Path):
        path = tmp_path / "skip-events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"test":"t1","reason":"x"}\nnot-json\n')
        with pytest.raises(RuntimeError) as exc:
            aggregate_skip_events(tmp_path)
        assert "Malformed JSONL" in str(exc.value)


class TestCheckThresholds:
    def test_empty_counts_passes(self):
        passed, msgs = check_thresholds(
            {}, total_tests=100, threshold=0.05,
        )
        assert passed is True
        assert msgs == []

    def test_under_threshold_passes(self):
        from collections import Counter
        passed, msgs = check_thresholds(
            Counter({"S3 not reachable": 3}),
            total_tests=100, threshold=0.05,
        )
        assert passed is True
        assert "[ok]" in msgs[0]
        assert "3.0%" in msgs[0]

    def test_over_threshold_fails(self):
        from collections import Counter
        passed, msgs = check_thresholds(
            Counter({"S3 not reachable": 10}),
            total_tests=100, threshold=0.05,
        )
        assert passed is False
        assert "[FAIL]" in msgs[0]
        assert "10.0%" in msgs[0]

    def test_one_reason_over_fails_even_if_others_under(self):
        from collections import Counter
        passed, msgs = check_thresholds(
            Counter({"S3 not reachable": 10, "Semantic not importable": 2}),
            total_tests=100, threshold=0.05,
        )
        assert passed is False
        # Every reason appears in messages, regardless of pass/fail
        assert len(msgs) == 2

    def test_rejects_zero_total_tests(self):
        from collections import Counter
        with pytest.raises(ValueError):
            check_thresholds(Counter(), total_tests=0, threshold=0.05)

    def test_rejects_negative_total_tests(self):
        from collections import Counter
        with pytest.raises(ValueError):
            check_thresholds(Counter(), total_tests=-1, threshold=0.05)

    def test_rejects_threshold_not_between_0_and_1(self):
        from collections import Counter
        with pytest.raises(ValueError):
            check_thresholds(Counter(), total_tests=100, threshold=0)
        with pytest.raises(ValueError):
            check_thresholds(Counter(), total_tests=100, threshold=1)
        with pytest.raises(ValueError):
            check_thresholds(Counter(), total_tests=100, threshold=-0.1)


class TestCLIEntrypoint:
    def test_main_exits_zero_when_under_threshold(self, tmp_path: Path, capsys):
        _write_jsonl(
            tmp_path / "skip-events.jsonl",
            [{"test": "t1", "reason": "S3 not reachable"}],
        )
        code = main([
            "--artifact-dir", str(tmp_path),
            "--total-tests", "100",
            "--threshold", "0.05",
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "[ok]" in out

    def test_main_exits_nonzero_when_over_threshold(self, tmp_path: Path, capsys):
        _write_jsonl(
            tmp_path / "skip-events.jsonl",
            [{"test": f"t{i}", "reason": "S3 not reachable"} for i in range(10)],
        )
        code = main([
            "--artifact-dir", str(tmp_path),
            "--total-tests", "100",
            "--threshold", "0.05",
        ])
        assert code == 1
        out = capsys.readouterr().out
        assert "[FAIL]" in out
        assert "::error" in out

    def test_main_with_no_artifact_dir_exits_zero(self, tmp_path: Path, capsys):
        code = main([
            "--artifact-dir", str(tmp_path / "nonexistent"),
            "--total-tests", "100",
            "--threshold", "0.05",
        ])
        assert code == 0
        assert "No skip events found" in capsys.readouterr().out
