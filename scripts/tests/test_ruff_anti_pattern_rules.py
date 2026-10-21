"""Ruff anti-pattern rules wiring TDD (Phase T.1 / W13).

The anti-patterns classes ``BLE`` (flake8-blind-except) and ``PT``
(flake8-pytest-style) were never enabled ANYWHERE: ``.ruff.toml``'s
``select`` omitted both and the ``tests/**`` per-file-ignore relaxes only
``PLR2004``/``S101`` — so blind ``except Exception: pass`` blocks and
pytest anti-patterns (e.g. ``pytest.raises`` without ``match``) have
silently linted clean in every test tree, paid and core alike.

These tests run the REAL ruff with the REAL repo config (``--config
.ruff.toml``) against synthetic offenders — no mocks, no stubs. A
synthetic offender that ruff does not flag fails the suite; that is the
RED that must hold until the rules are enabled in the repo config (both
.ruff.toml AND the pyproject mirror — GATE-34 enforces the mirror).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUFF_CONFIG = REPO_ROOT / ".ruff.toml"


def _ruff_check(source: str, filename: str, tmp_path: Path) -> subprocess.CompletedProcess:
    target = tmp_path / filename
    target.write_text(source, encoding="utf-8")
    return subprocess.run(
        ["ruff", "check", "--config", str(RUFF_CONFIG), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


class TestBlindExceptEnabled:
    def test_blind_except_pass_is_flagged_by_the_repo_config(self, tmp_path):
        """BLE001: a blind ``except Exception: pass`` must FAIL the repo's
        ruff config — the class that silently swallowed production errors
        (and masked test failures) for years."""
        result = _ruff_check(
            "def load():\n    try:\n        return int('x')\n    except Exception:\n        pass\n",
            "offender_blind_except.py",
            tmp_path,
        )
        assert result.returncode != 0, (
            f"ruff must flag the blind except; stdout={result.stdout} stderr={result.stderr}"
        )
        assert "BLE001" in result.stdout + result.stderr, result.stdout + result.stderr

    def test_narrow_except_still_passes(self, tmp_path):
        """Narrow exception handling must remain clean — the rule targets
        the blind form only."""
        result = _ruff_check(
            "def load():\n"
            "    try:\n"
            "        return int('x')\n"
            "    except ValueError:\n"
            "        return 0\n",
            "clean_narrow_except.py",
            tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestPytestStyleEnabled:
    def test_pytest_raises_without_match_is_flagged(self, tmp_path):
        """PT011: ``pytest.raises(X)`` without ``match`` must fail — the
        form that passes even when the wrong exception fires."""
        result = _ruff_check(
            "import pytest\n\n"
            "def test_explodes():\n"
            "    with pytest.raises(ValueError):\n"
            "        raise ValueError('boom')\n",
            "test_offender_pt011.py",
            tmp_path,
        )
        assert result.returncode != 0, result.stdout + result.stderr
        assert "PT011" in result.stdout + result.stderr, result.stdout + result.stderr

    def test_pytest_raises_with_match_still_passes(self, tmp_path):
        result = _ruff_check(
            "import pytest\n\n\n"
            "def test_explodes():\n"
            "    with pytest.raises(ValueError, match='boom'):\n"
            "        raise ValueError('boom')\n",
            "test_clean_pt011.py",
            tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestConfigMirror:
    def test_pyproject_mirror_lists_the_same_rules(self, tmp_path):
        """W2.1: the pyproject mirror must carry BLE + PT too — GATE-34
        compares the two ``lint.select`` lists; a divergence is dead
        config."""
        import tomllib

        with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
            pyproject_select = tomllib.load(fh)["tool"]["ruff"]["lint"]["select"]
        with open(RUFF_CONFIG, "rb") as fh:
            ruff_select = tomllib.load(fh)["lint"]["select"]
        assert "BLE" in ruff_select, ".ruff.toml select must include BLE"
        assert "PT" in ruff_select, ".ruff.toml select must include PT"
        assert sorted(ruff_select) == sorted(pyproject_select), (
            "the .ruff.toml and pyproject.toml select lists diverged (GATE-34 will fail too)"
        )

    def test_tests_are_not_exempted_from_the_new_rules(self, tmp_path):
        """Test-tree ignores relax only the unittest-idiom PT rules
        (PT009/PT027/PT012/PT013/PT021 — the Django TestCase
        ``self.assert*`` surface, 2026-09-28 cilint policy) plus
        PLR2004/S101 and the pytest-injected ARG noise. BLE001 and the
        remaining PT rules (PT011 etc.) must still bite IN TEST TREES —
        that is the whole point: they were never enabled anywhere, not
        suppressed in tests."""
        import tomllib

        with open(RUFF_CONFIG, "rb") as fh:
            per_file = tomllib.load(fh)["lint"]["per-file-ignores"]
        allowed_test_tree_ignores = {
            "PLR2004",
            "S101",
            "PT009",
            "PT027",
            "PT012",
            "PT013",
            "PT021",
            "ARG001",
            "ARG002",
            "ARG005",
        }
        for glob_pattern, ignores in per_file.items():
            if "tests" in glob_pattern:
                for code in ("BLE",):
                    assert not any(i == code or i.startswith(code) for i in ignores), (
                        f"{glob_pattern} suppresses {code} — BLE001 must apply to test files"
                    )
                for code in ignores:
                    if code.startswith("PT"):
                        assert code in allowed_test_tree_ignores, (
                            f"{glob_pattern} suppresses {code} — only the "
                            "unittest-idiom PT rules may be ignored in test trees"
                        )
