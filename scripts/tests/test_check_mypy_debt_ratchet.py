"""check_mypy_debt_ratchet.py tests — REAL mypy subprocess over synthetic
repos, no mocks. The gate is only as good as its ability to fail on real
growth, so every test drives the actual gate + actual mypy binary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_mypy_debt_ratchet import main, run_mypy

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Minimal mypy config for the synthetic repos: no excludes, so a single
# bad file produces exactly one error line.
SYNTH_CONFIG = "[mypy]\npython_version = 3.12\n"
SYNTH_BAD = "x: int = 'not-an-int'\n"


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _baseline(total: int) -> str:
    return json.dumps({"total": total}, indent=2, sort_keys=True)


class TestRules:
    def test_identical_counts_pass(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "mypy_debt_baseline.json", _baseline(1))
        assert (
            main(["--root", str(tmp_path), "--baseline", str(tmp_path / "mypy_debt_baseline.json")])
            == 0
        )

    def test_growth_fails(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "b.py", SYNTH_BAD)
        _write(tmp_path, "mypy_debt_baseline.json", _baseline(1))
        assert (
            main(["--root", str(tmp_path), "--baseline", str(tmp_path / "mypy_debt_baseline.json")])
            == 1
        )

    def test_reduction_passes(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "mypy_debt_baseline.json", _baseline(2))
        assert (
            main(["--root", str(tmp_path), "--baseline", str(tmp_path / "mypy_debt_baseline.json")])
            == 0
        )

    def test_update_writes_then_passes(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        baseline = tmp_path / "mypy_debt_baseline.json"
        assert main(["--root", str(tmp_path), "--baseline", str(baseline), "--update"]) == 0
        assert json.loads(baseline.read_text())["total"] == 1
        assert main(["--root", str(tmp_path), "--baseline", str(baseline)]) == 0

    def test_missing_baseline_is_usage_error(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        assert main(["--root", str(tmp_path), "--baseline", str(tmp_path / "nope.json")]) == 2

    def test_crash_is_usage_error_not_growth(self, tmp_path):
        """mypy rc 2 (e.g. the Q.1.1 dotted-dir crash) must read as a gate
        failure, never as a clean pass."""
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "mypy_debt_baseline.json", _baseline(0))
        count, error = run_mypy(tmp_path / "does-not-exist-dir")
        assert count is None
        assert "crashed" in error

    def test_run_mypy_counts_error_lines(self, tmp_path):
        _write(tmp_path, "mypy.ini", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "b.py", SYNTH_BAD)
        count, error = run_mypy(tmp_path)
        assert error is None
        assert count == 2


class TestRealRepo:
    def test_real_repo_passes_committed_baseline(self):
        assert main(["--root", str(REPO_ROOT)]) == 0
