"""check_config_single_source.py tests — TDD fixtures, no mocks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_config_single_source import collect_violations, main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestRules:
    def test_single_source_passes(self, tmp_path):
        _write(tmp_path, "pyproject.toml", "[tool.ruff]\nline-length = 100\n")
        assert collect_violations(tmp_path) == []

    def test_dedicated_file_only_passes(self, tmp_path):
        _write(tmp_path, ".ruff.toml", "line-length = 100\n")
        assert collect_violations(tmp_path) == []

    def test_divergent_duplicate_fails(self, tmp_path):
        """THE drift class: .ruff.toml shadows a DIFFERENT pyproject value."""
        _write(tmp_path, ".ruff.toml", "line-length = 100\n")
        _write(tmp_path, "pyproject.toml", "[tool.ruff]\nline-length = 88\n")
        violations = collect_violations(tmp_path)
        assert any("ruff" in v and "line-length" in v for v in violations)

    def test_equivalent_mirror_passes(self, tmp_path):
        """The documented reconciliation pattern: both exist, values match."""
        _write(tmp_path, ".ruff.toml", 'line-length = 100\ntarget-version = "py312"\n')
        _write(
            tmp_path,
            "pyproject.toml",
            '[tool.ruff]\nline-length = 100\ntarget-version = "py312"\n',
        )
        assert collect_violations(tmp_path) == []

    def test_mypy_ini_divergence_fails(self, tmp_path):
        _write(tmp_path, "mypy.ini", "[mypy]\npython_version = 3.12\n")
        _write(tmp_path, "pyproject.toml", '[tool.mypy]\npython_version = "3.11"\n')
        violations = collect_violations(tmp_path)
        assert any("mypy" in v and "python_version" in v for v in violations)

    def test_unconfigured_tool_is_clean(self, tmp_path):
        assert collect_violations(tmp_path) == []


class TestNestedSections:
    """The real drift classes: keys that live under sub-tables/sections."""

    def test_ruff_lint_select_divergence_fails(self, tmp_path):
        """[lint] select lives under a sub-table — must be compared."""
        _write(tmp_path, ".ruff.toml", '[lint]\nselect = ["E", "F"]\n')
        _write(tmp_path, "pyproject.toml", '[tool.ruff.lint]\nselect = ["E", "F", "DTZ"]\n')
        violations = collect_violations(tmp_path)
        assert any("ruff" in v and "lint.select" in v for v in violations)

    def test_ruff_lint_ignore_divergence_fails(self, tmp_path):
        _write(tmp_path, ".ruff.toml", '[lint]\nignore = ["E501"]\n')
        _write(tmp_path, "pyproject.toml", "[tool.ruff.lint]\nignore = []\n")
        violations = collect_violations(tmp_path)
        assert any("ruff" in v and "lint.ignore" in v for v in violations)

    def test_ruff_nested_mirror_passes(self, tmp_path):
        _write(
            tmp_path,
            ".ruff.toml",
            'line-length = 100\n[lint]\nselect = ["E", "F"]\nignore = ["E501"]\n',
        )
        _write(
            tmp_path,
            "pyproject.toml",
            '[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ["E", "F"]\nignore = ["E501"]\n',
        )
        assert collect_violations(tmp_path) == []

    def test_ruff_select_order_is_significant(self, tmp_path):
        """select order sets rule precedence — reordering IS a divergence."""
        _write(tmp_path, ".ruff.toml", '[lint]\nselect = ["E", "F"]\n')
        _write(tmp_path, "pyproject.toml", '[tool.ruff.lint]\nselect = ["F", "E"]\n')
        violations = collect_violations(tmp_path)
        assert any("ruff" in v and "lint.select" in v for v in violations)

    def test_mypy_per_module_divergence_fails(self, tmp_path):
        """[mypy-*] sections vs [[tool.mypy.overrides]] — the class that
        rotted before (Phase 250.DoD.R10 added a section to mypy.ini only)."""
        _write(
            tmp_path,
            "mypy.ini",
            "[mypy]\npython_version = 3.12\n[mypy-requests.*]\nignore_missing_imports = true\n",
        )
        _write(
            tmp_path,
            "pyproject.toml",
            '[tool.mypy]\npython_version = "3.12"\n'
            '[[tool.mypy.overrides]]\nmodule = ["django.*"]\nignore_missing_imports = true\n',
        )
        violations = collect_violations(tmp_path)
        assert any("mypy" in v and "per-module" in v for v in violations)

    def test_mypy_per_module_equivalent_passes(self, tmp_path):
        _write(
            tmp_path,
            "mypy.ini",
            "[mypy]\npython_version = 3.12\n[mypy-requests.*]\nignore_missing_imports = true\n",
        )
        _write(
            tmp_path,
            "pyproject.toml",
            '[tool.mypy]\npython_version = "3.12"\n'
            '[[tool.mypy.overrides]]\nmodule = ["requests.*"]\nignore_missing_imports = true\n',
        )
        assert collect_violations(tmp_path) == []

    def test_coverage_run_nesting_diverges(self, tmp_path):
        _write(tmp_path, ".coveragerc", "[run]\nsource = hub\n")
        _write(tmp_path, "pyproject.toml", '[tool.coverage.run]\nsource = ["other"]\n')
        violations = collect_violations(tmp_path)
        assert any("coverage" in v and "run.source" in v for v in violations)

    def test_bandit_divergence_fails(self, tmp_path):
        _write(tmp_path, ".bandit", "[bandit]\nskips = B101\n")
        _write(tmp_path, "pyproject.toml", '[tool.bandit]\nskips = ["B110"]\n')
        violations = collect_violations(tmp_path)
        assert any("bandit" in v and "skips" in v for v in violations)

    def test_bandit_yaml_config_parses_without_crashing(self, tmp_path):
        """Bandit 1.8+ configs are YAML, not INI — the gate must handle both
        (the Q.1 review converted the repo's .bandit to YAML)."""
        _write(tmp_path, ".bandit", 'skips: ["B101"]\nexclude_dirs: [".git"]\n')
        _write(tmp_path, "pyproject.toml", '[tool.bandit]\nskips = ["B110"]\n')
        violations = collect_violations(tmp_path)
        assert any("bandit" in v and "skips" in v for v in violations)

    def test_bandit_yaml_single_source_passes(self, tmp_path):
        _write(tmp_path, ".bandit", 'skips: ["B101"]\n')
        assert collect_violations(tmp_path) == []

    def test_pytest_ini_options_divergence_fails(self, tmp_path):
        """pytest reads [tool.pytest.ini_options], not [tool.pytest]."""
        _write(tmp_path, "pytest.ini", "[pytest]\naddopts = --strict-markers\n")
        _write(
            tmp_path,
            "pyproject.toml",
            '[tool.pytest.ini_options]\naddopts = "--strict-markers --tb=long"\n',
        )
        violations = collect_violations(tmp_path)
        assert any("pytest" in v and "addopts" in v for v in violations)

    def test_pytest_flat_tool_section_is_dead_config(self, tmp_path):
        """[tool.pytest] (flat) is NEVER read by pytest — dead config."""
        _write(tmp_path, "pytest.ini", "[pytest]\naddopts = --strict-markers\n")
        _write(tmp_path, "pyproject.toml", '[tool.pytest]\naddopts = "--strict-markers"\n')
        violations = collect_violations(tmp_path)
        assert any("pytest" in v and "never read" in v for v in violations)


class TestRealRepo:
    def test_real_repo_is_single_source_or_documented_mirror(self):
        assert main(["--root", str(REPO_ROOT)]) == 0
