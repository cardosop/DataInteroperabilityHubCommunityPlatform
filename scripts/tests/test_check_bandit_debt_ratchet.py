"""check_bandit_debt_ratchet.py tests — REAL bandit subprocess over synthetic
targets, no mocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_bandit_debt_ratchet import main, run_bandit

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# A real bandit finding: shell=True on a subprocess call (B602).
SYNTH_BAD = "import subprocess\n\n\ndef run(cmd):\n    subprocess.call(cmd, shell=True)\n"
# Minimal YAML bandit config (the INI form is the parse-crash class).
SYNTH_CONFIG = "skips: []\n"


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _baseline(total: int) -> str:
    return json.dumps({"total": total}, indent=2, sort_keys=True)


class TestRules:
    def test_identical_counts_pass(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "bandit_debt_baseline.json", _baseline(1))
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(tmp_path / "bandit_debt_baseline.json"),
                ]
            )
            == 0
        )

    def test_growth_fails(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "b.py", SYNTH_BAD)
        _write(tmp_path, "bandit_debt_baseline.json", _baseline(1))
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(tmp_path / "bandit_debt_baseline.json"),
                ]
            )
            == 1
        )

    def test_reduction_passes(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "bandit_debt_baseline.json", _baseline(2))
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(tmp_path / "bandit_debt_baseline.json"),
                ]
            )
            == 0
        )

    def test_update_writes_then_passes(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        baseline = tmp_path / "bandit_debt_baseline.json"
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(baseline),
                    "--update",
                ]
            )
            == 0
        )
        assert json.loads(baseline.read_text())["total"] == 1
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(baseline),
                ]
            )
            == 0
        )

    def test_unparseable_config_is_usage_error_not_clean(self, tmp_path):
        """The .bandit INI-format trap: a config bandit cannot parse must
        read as a GATE failure (the old || true masked it as green)."""
        _write(tmp_path, "cfg.yml", "[bandit]\nskips = B101\n")  # INI, invalid YAML
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "bandit_debt_baseline.json", _baseline(0))
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(tmp_path / "bandit_debt_baseline.json"),
                ]
            )
            == 2
        )

    def test_missing_baseline_is_usage_error(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        assert (
            main(
                [
                    "--targets",
                    str(tmp_path),
                    "--config",
                    str(tmp_path / "cfg.yml"),
                    "--baseline",
                    str(tmp_path / "nope.json"),
                ]
            )
            == 2
        )

    def test_run_bandit_counts_issues(self, tmp_path):
        _write(tmp_path, "cfg.yml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", SYNTH_BAD)
        _write(tmp_path, "b.py", SYNTH_BAD)
        count, error = run_bandit([str(tmp_path)], str(tmp_path / "cfg.yml"))
        assert error is None
        assert count == 2


class TestRealRepo:
    def test_real_repo_passes_committed_baseline(self):
        assert main([]) == 0
