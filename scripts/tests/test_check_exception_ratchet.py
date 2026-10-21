"""GATE-58 (oss-release-remediation W12.3) pins — no mocks, no stubs.

The RED phase of W12.3: the pins below ran against the REAL repository
before the baselines landed and failed (no committed exception/noqa
inventory existed; the §1.2 register's "445 broad except / 341 noqa"
was the 2026-10-05 assessment — the real inventory at gate time is
2,162 broad-except sites across 539 non-test hub files, 1,290 ``# noqa``
comments repo-wide, and ZERO bare excepts (the register's "2" were
already fixed)).

Pins exercise the REAL gate as a subprocess against:
  * the real repository (master GREEN pins),
  * planted-violation temp git repos (the gate BITES — an untriaged
    broad except, a bare except, a new noqa, a dead/over-broad/
    reasonless allowlist entry, or baseline growth vs HEAD flips it RED),
  * finder-precision temp trees (specific catches are NOT sites, catch
    tuples ARE, tests/migrations/conftest are out of scope, line-shift
    churn is free — the GATE-29 accounting contract).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_exception_ratchet.py"
EXC_BASELINE = REPO_ROOT / "scripts" / "exception_baseline.json"
EXC_ALLOWLIST = REPO_ROOT / "scripts" / "exception_allowlist.json"
NOQA_BASELINE = REPO_ROOT / "scripts" / "noqa_baseline.json"


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_repo(
    tmp_path: Path,
    files: dict[str, str],
    exc_baseline: dict[str, list[int]] | None = None,
    exc_allowlist: dict[str, dict] | None = None,
    noqa_baseline: dict[str, int] | None = None,
) -> Path:
    """A real git repo with hub/ tree + committed gate baselines."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, content in files.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content)
    scripts = repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "exception_baseline.json").write_text(
        json.dumps({"files": exc_baseline or {}}, indent=2)
    )
    (scripts / "exception_allowlist.json").write_text(
        json.dumps({"files": exc_allowlist or {}}, indent=2)
    )
    (scripts / "noqa_baseline.json").write_text(
        json.dumps({"files": noqa_baseline or {}}, indent=2)
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "pin@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "pin"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    return repo


_BROAD = "def f():\n    try:\n        risky()\n    except Exception:\n        pass\n"
_BARE = "def f():\n    try:\n        risky()\n    except:\n        pass\n"
_SPECIFIC = (
    "def f():\n    try:\n        risky()\n    except ValueError:\n        pass\n"
)


class TestRealRepository:
    """The master GREEN pins — the real tree satisfies the whole contract."""

    def test_real_repo_exception_gate_passes(self):
        result = _run_gate("--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "exception ratchet clean" in result.stdout
        growth = _run_gate("--check-growth")
        assert growth.returncode == 0, growth.stdout + growth.stderr

    def test_real_repo_noqa_gate_passes(self):
        result = _run_gate("--check-noqa")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "noqa ratchet clean" in result.stdout
        growth = _run_gate("--check-noqa-growth")
        assert growth.returncode == 0, growth.stdout + growth.stderr

    def test_real_repo_has_no_bare_excepts(self):
        import ast

        for path in (REPO_ROOT / "hub").rglob("*.py"):
            rel = str(path.relative_to(REPO_ROOT))
            parts = rel.split("/")
            if (
                "tests" in parts
                or "migrations" in parts
                or "testing" in parts
                or path.name.startswith("conftest")
            ):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    pytest.fail(f"bare except reintroduced: {rel}:{node.lineno}")

    def test_real_repo_allowlist_entries_are_reasoned_and_live(self):
        payload = json.loads(EXC_ALLOWLIST.read_text(encoding="utf-8"))
        for path, entry in sorted(payload["files"].items()):
            assert (REPO_ROOT / path).is_file(), f"{path}: dead allowlist anchor"
            reason = entry.get("reason", "")
            assert reason, f"{path}: allowlist entry reason is empty"
            assert not reason.startswith(
                "TODO"
            ), f"{path}: allowlist entry needs a reason"

    def test_ruff_ble001_remains_enabled(self):
        # W12.3's "enable ruff BLE001" shipped in Phase T.1 — this pin
        # keeps it from being silently reverted (unselecting BLE would
        # free the debt from GATE-35's global ratchet).
        ruff_toml = (REPO_ROOT / ".ruff.toml").read_text(encoding="utf-8")
        has_ble_select = '"BLE"' in ruff_toml or "'BLE'" in ruff_toml
        assert has_ble_select, "BLE must stay in the ruff select list"
        debt = json.loads(
            (REPO_ROOT / "scripts" / "lint_debt_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        assert "BLE001" in debt["rules"]


class TestPlantedViolationsBite:
    """Drift pins — reintroducing any class flips the gate RED."""

    def test_planted_untriaged_broad_except_bites(self, tmp_path):
        repo = _make_repo(tmp_path, {"hub/apps/x/mod.py": _BROAD})
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "untriaged broad except site" in result.stdout
        assert "mod.py" in result.stdout

    def test_planted_bare_except_bites(self, tmp_path):
        repo = _make_repo(tmp_path, {"hub/apps/x/mod.py": _BARE})
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "bare except" in result.stdout

    def test_planted_new_noqa_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": "x = 1  # noqa: E999\n"},
        )
        result = _run_gate("--root", str(repo), "--check-noqa")
        assert result.returncode == 1
        assert "noqa" in result.stdout
        assert "mod.py" in result.stdout

    def test_planted_dead_allowlist_anchor_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/__init__.py": ""},
            exc_allowlist={"hub/apps/x/gone.py": {"allowed": 1, "reason": "stale"}},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "gone.py" in result.stdout

    def test_planted_over_broad_allowlist_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": _BROAD},
            exc_allowlist={"hub/apps/x/mod.py": {"allowed": 5, "reason": "telemetry"}},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "over-broad" in result.stdout

    def test_planted_reasonless_allowlist_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": _BROAD},
            exc_allowlist={
                "hub/apps/x/mod.py": {"allowed": 1, "reason": "TODO: reason"}
            },
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "reason" in result.stdout

    def test_planted_stale_baseline_entry_bites(self, tmp_path):
        # The file is clean but the baseline still lists it — the shrink
        # path must be completed by removing the entry.
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": _SPECIFIC},
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "stale" in result.stdout

    def test_exception_baseline_growth_bites_vs_head(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": _BROAD},
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )
        base = repo / "scripts" / "exception_baseline.json"
        payload = json.loads(base.read_text(encoding="utf-8"))
        payload["files"]["hub/apps/x/other.py"] = [4]
        base.write_text(json.dumps(payload, indent=2))
        result = _run_gate("--root", str(repo), "--check-growth")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "other.py" in result.stdout

    def test_allowlist_growth_bites_vs_head(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": _BROAD},
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )
        allow = repo / "scripts" / "exception_allowlist.json"
        payload = json.loads(allow.read_text(encoding="utf-8"))
        payload["files"]["hub/apps/x/mod.py"] = {
            "allowed": 1,
            "reason": "telemetry boundary",
        }
        allow.write_text(json.dumps(payload, indent=2))
        result = _run_gate("--root", str(repo), "--check-growth")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "mod.py" in result.stdout

    def test_noqa_baseline_growth_bites_vs_head(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": "x = 1  # noqa: E999\n"},
            noqa_baseline={"hub/apps/x/mod.py": 1},
        )
        base = repo / "scripts" / "noqa_baseline.json"
        payload = json.loads(base.read_text(encoding="utf-8"))
        payload["files"]["hub/apps/x/other.py"] = 2
        base.write_text(json.dumps(payload, indent=2))
        result = _run_gate("--root", str(repo), "--check-noqa-growth")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "other.py" in result.stdout

    def test_working_noqa_growth_bites_vs_baseline(self, tmp_path):
        # Working tree has 2 noqas, the baseline recorded 1 — the
        # inventory is incomplete: a NEW noqa needs review.
        repo = _make_repo(
            tmp_path,
            {"hub/apps/x/mod.py": "x = 1  # noqa: E999\n# noqa: E999\n"},
            noqa_baseline={"hub/apps/x/mod.py": 1},
        )
        result = _run_gate("--root", str(repo), "--check-noqa")
        assert result.returncode == 1
        assert "review" in result.stdout


class TestFinderPrecision:
    """Root-cause pins — the scanner's scope and accounting contract."""

    def _check_passes(
        self,
        tree: dict[str, str],
        tmp_path: Path,
        exc_baseline: dict[str, list[int]] | None = None,
        noqa_baseline: dict[str, int] | None = None,
        mode: str = "--check",
    ) -> Path:
        repo = tmp_path / "tree"
        repo.mkdir()
        for rel, content in tree.items():
            dst = repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content)
        scripts = repo / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "exception_baseline.json").write_text(
            json.dumps({"files": exc_baseline or {}}, indent=2)
        )
        (scripts / "exception_allowlist.json").write_text(
            json.dumps({"files": {}}, indent=2)
        )
        (scripts / "noqa_baseline.json").write_text(
            json.dumps({"files": noqa_baseline or {}}, indent=2)
        )
        result = _run_gate("--root", str(repo), mode)
        assert result.returncode == 0, result.stdout + result.stderr
        return repo

    def test_specific_catch_is_not_a_site(self, tmp_path):
        self._check_passes({"hub/apps/x/mod.py": _SPECIFIC}, tmp_path)

    def test_catch_tuple_with_exception_is_a_site(self, tmp_path):
        source = (
            "def f():\n    try:\n        risky()\n"
            "    except (ValueError, Exception):\n        pass\n"
        )
        self._check_passes(
            {"hub/apps/x/mod.py": source},
            tmp_path,
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )

    def test_catch_tuple_without_exception_is_not_a_site(self, tmp_path):
        source = (
            "def f():\n    try:\n        risky()\n"
            "    except (ValueError, TypeError):\n        pass\n"
        )
        self._check_passes({"hub/apps/x/mod.py": source}, tmp_path)

    def test_baseexception_is_a_site(self, tmp_path):
        source = (
            "def f():\n    try:\n        risky()\n"
            "    except BaseException:\n        pass\n"
        )
        self._check_passes(
            {"hub/apps/x/mod.py": source},
            tmp_path,
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )

    def test_tests_and_migrations_are_out_of_scope(self, tmp_path):
        self._check_passes(
            {
                "hub/apps/x/mod.py": _SPECIFIC,
                "hub/apps/x/tests/test_mod.py": _BROAD,
                "hub/apps/x/migrations/0001_initial.py": _BROAD,
                "hub/conftest.py": _BROAD,
                "hub/apps/testing/helper.py": _BROAD,
            },
            tmp_path,
        )

    def test_line_shift_churn_is_free(self, tmp_path):
        # Same file, same count, different lines — churn, not growth
        # (the GATE-29 allowlist accounting contract). The baseline
        # pinned line 4; the site moved to line 8.
        source = (
            "def f():\n"
            "    try:\n"
            "        risky()\n"
            "    except ValueError:\n"
            "        pass\n"
            "    try:\n"
            "        risky2()\n"
            "    except Exception:\n"
            "        pass\n"
        )
        repo = self._check_passes(
            {"hub/apps/x/mod.py": source},
            tmp_path,
            exc_baseline={"hub/apps/x/mod.py": [4]},
        )
        # Also verify the churn holds for --check-growth: baseline was
        # committed as-is, working tree unchanged → clean.
        result = _run_gate("--root", str(repo), "--check-growth")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_shrink_passes_and_reports_delta(self, tmp_path):
        # Two baselined sites, one remains — shrink, clean, and the
        # delta is reported (the stale-to-zero case FAILS by design:
        # the entry must be removed, see test_planted_stale_baseline).
        repo = self._check_passes(
            {"hub/apps/x/mod.py": _BROAD},
            tmp_path,
            exc_baseline={"hub/apps/x/mod.py": [4, 10]},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert "shrink: 1" in result.stdout

    def test_noqa_counting_is_per_file(self, tmp_path):
        self._check_passes(
            {
                "hub/apps/x/mod.py": "x = 1  # noqa: E999\n",
                "hub/apps/y/other.py": "y = 1\n",
            },
            tmp_path,
            noqa_baseline={"hub/apps/x/mod.py": 1},
            mode="--check-noqa",
        )

    def test_allowlisted_sites_are_not_debt(self, tmp_path):
        # The whole file is allowlisted as a boundary catch → no debt,
        # and the baseline may stay empty for it. The tree is built by
        # hand (no pre-check run — the untriaged state is meant to fail).
        repo = tmp_path / "tree"
        dst = repo / "hub" / "apps" / "x" / "mod.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_BROAD)
        scripts = repo / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "exception_baseline.json").write_text(
            json.dumps({"files": {}}, indent=2)
        )
        (scripts / "exception_allowlist.json").write_text(
            json.dumps(
                {
                    "files": {
                        "hub/apps/x/mod.py": {
                            "allowed": 1,
                            "reason": "telemetry emitter — recording "
                            "must never fail the caller",
                        }
                    }
                },
                indent=2,
            )
        )
        (scripts / "noqa_baseline.json").write_text(json.dumps({"files": {}}, indent=2))
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 0, result.stdout + result.stderr
