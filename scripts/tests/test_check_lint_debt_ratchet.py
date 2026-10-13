"""check_lint_debt_ratchet.py tests — REAL ruff subprocess over synthetic
repos, no mocks. The ratchet is only as good as its ability to fail on
real growth, so every test drives the actual gate + actual ruff binary."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_lint_debt_ratchet import compare, main

RUFF = shutil.which("ruff")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Minimal ruff config for the synthetic repos: pyflakes only, so findings
# are deterministic and independent of the host repo's config.
SYNTH_CONFIG = '[lint]\nselect = ["F401", "E722"]\n'


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _baseline(rules: dict, total: int | None = None) -> str:
    payload = {"total": total if total is not None else sum(rules.values()), "rules": rules}
    return json.dumps(payload, indent=2, sort_keys=True)


class TestRules:
    def test_identical_counts_pass(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "import os\n\n\ndef f():\n    pass\n")
        _write(tmp_path, "lint_debt_baseline.json", _baseline({"F401": 1}))
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "lint_debt_baseline.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 0
        )

    def test_growth_fails_naming_the_rule(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "import os\nimport sys\n")
        _write(tmp_path, "lint_debt_baseline.json", _baseline({"F401": 1}))
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "lint_debt_baseline.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 1
        )

    def test_reduction_passes(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "import os\n")
        _write(tmp_path, "lint_debt_baseline.json", _baseline({"F401": 2}))
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "lint_debt_baseline.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 0
        )

    def test_new_rule_without_baseline_fails(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "try:\n    pass\nexcept:\n    pass\n")
        _write(tmp_path, "lint_debt_baseline.json", _baseline({}))
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "lint_debt_baseline.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 1
        )

    def test_line_shift_is_net_zero(self, tmp_path):
        """Net-accounting: a finding moving between files must NOT fail."""
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "b.py", "import os\n")
        _write(tmp_path, "lint_debt_baseline.json", _baseline({"F401": 1}))
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "lint_debt_baseline.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 0
        )

    def test_update_writes_then_passes(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "import os\nimport sys\n")
        baseline = tmp_path / "lint_debt_baseline.json"
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(baseline),
                    "--ruff-binary",
                    RUFF,
                    "--update",
                ]
            )
            == 0
        )
        written = json.loads(baseline.read_text())
        assert written["rules"]["F401"] == 2
        assert written["total"] == 2
        assert (
            main(["--root", str(tmp_path), "--baseline", str(baseline), "--ruff-binary", RUFF]) == 0
        )

    def test_missing_baseline_is_usage_error(self, tmp_path):
        _write(tmp_path, ".ruff.toml", SYNTH_CONFIG)
        _write(tmp_path, "a.py", "import os\n")
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "nope.json"),
                    "--ruff-binary",
                    RUFF,
                ]
            )
            == 2
        )

    def test_missing_ruff_is_usage_error(self, tmp_path):
        _write(tmp_path, "a.py", "import os\n")
        assert (
            main(
                [
                    "--root",
                    str(tmp_path),
                    "--baseline",
                    str(tmp_path / "b.json"),
                    "--ruff-binary",
                    "/nonexistent/ruff",
                ]
            )
            == 2
        )


class TestCompareUnit:
    def test_compare_flags_growth_and_new_rules(self):
        violations = compare({"F401": 3, "E722": 1}, {"rules": {"F401": 2}})
        assert any("F401" in v and "3 > baseline 2" in v for v in violations)
        assert any("E722" in v and "no baseline entry" in v for v in violations)

    def test_compare_clean_on_equal_and_under(self):
        assert compare({"F401": 2}, {"rules": {"F401": 2}}) == []
        assert compare({"F401": 1}, {"rules": {"F401": 2}}) == []


class TestRealRepo:
    def test_real_repo_passes_committed_baseline(self):
        assert main(["--root", str(REPO_ROOT), "--ruff-binary", RUFF]) == 0
