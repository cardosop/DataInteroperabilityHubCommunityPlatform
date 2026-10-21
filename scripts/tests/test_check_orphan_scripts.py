"""GATE-59 (oss-release-remediation W12.4) pins — no mocks, no stubs.

The RED phase of W12.4: the pins below ran against the REAL repository
before the triage landed and failed — 70 orphaned quality scripts
(check_*/lint_*/audit_*/verify_* with no reference from CI, Makefiles,
pre-commit, package.json, the CI pytest list, or any wired script) and
no committed wiring ledger.

Pins exercise the REAL gate as a subprocess against:
  * the real repository (master GREEN pins),
  * planted-violation temp git repos (an unwired script BITES; Makefile
    wiring, transitive full-path wiring, and the strict no-bare-mention
    edge rule are pinned; the ledger-honesty contract is pinned: a wired
    row must cite a surface that really references the script, a deleted
    row must name a file that no longer exists, and an untriaged script
    fails).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_orphan_scripts.py"
LEDGER = REPO_ROOT / "scripts" / "script_wiring_ledger.json"


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
    ledger: dict[str, dict] | None = None,
) -> Path:
    """A real git repo with scripts/, Makefile, and a committed ledger."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, content in files.items():
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content)
    scripts = repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "script_wiring_ledger.json").write_text(
        json.dumps(
            ledger if ledger is not None else {"wired": {}, "deleted": {}},
            indent=2,
        )
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


class TestRealRepository:
    """The master GREEN pins — the real tree satisfies the whole contract."""

    def test_real_repo_gate_passes(self):
        result = _run_gate("--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "orphan-script gate clean" in result.stdout

    def test_real_repo_ledger_is_committed_and_honest(self):
        payload = json.loads(LEDGER.read_text(encoding="utf-8"))
        for name, surface in sorted(payload["wired"].items()):
            assert (
                REPO_ROOT / surface
            ).is_file(), f"{name}: ledger cites missing surface {surface}"
            assert name in (REPO_ROOT / surface).read_text(
                encoding="utf-8", errors="replace"
            ), f"{name}: surface {surface} does not reference it"
        for name in sorted(payload["deleted"]):
            assert not (
                REPO_ROOT / "scripts" / name
            ).exists(), f"{name}: ledger says deleted but the script still exists"

    def test_real_repo_has_no_untriaged_scripts(self):
        import re

        for path in sorted((REPO_ROOT / "scripts").iterdir()):
            if not re.match(r"^(check|lint|audit|verify)_", path.name):
                continue
            if path.suffix not in {".py", ".sh", ".cjs", ".mjs"}:
                continue
            if path.name == "check_orphan_scripts.py":
                continue  # the gate self-exempts (its wiring is this contract)
            payload = json.loads(LEDGER.read_text(encoding="utf-8"))
            known = set(payload["wired"]) | set(payload["deleted"])
            assert path.name in known, f"{path.name}: untriaged script"


class TestPlantedViolationsBite:
    """Drift pins — an unwired script or an dishonest ledger flips RED."""

    def test_planted_unwired_script_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_planted.py": "print('hi')\n",
                "Makefile": "all:\n\t@echo ok\n",
            },
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "check_planted.py" in result.stdout

    def test_makefile_wiring_passes(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_ok.py": "print('hi')\n",
                "Makefile": "gate:\n\tpython scripts/check_ok.py\n",
            },
            ledger={"wired": {"check_ok.py": "Makefile"}, "deleted": {}},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_transitive_full_path_wiring_passes(self, tmp_path):
        # check_a.py is wired via the Makefile; it calls scripts/check_b.py
        # by full path — check_b.py is transitively wired.
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_a.py": (
                    "import subprocess\n"
                    "subprocess.run(['python', 'scripts/check_b.py'])\n"
                ),
                "scripts/check_b.py": "print('hi')\n",
                "Makefile": "gate:\n\tpython scripts/check_a.py\n",
            },
            ledger={
                "wired": {
                    "check_a.py": "Makefile",
                    "check_b.py": "scripts/check_a.py",
                },
                "deleted": {},
            },
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_bare_name_mention_does_not_wire(self, tmp_path):
        # A comment naming the script is NOT wiring — the strict edge
        # rule requires scripts/<name> or an import.
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_a.py": "# see check_b.py for details\nprint(1)\n",
                "scripts/check_b.py": "print('hi')\n",
                "Makefile": "gate:\n\tpython scripts/check_a.py\n",
            },
            ledger={"wired": {"check_a.py": "Makefile"}, "deleted": {}},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "check_b.py" in result.stdout

    def test_json_data_files_are_not_scripts(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"scripts/lint_debt_baseline.json": '{"rules": {}}\n'},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ledger_wired_row_citing_non_referencing_surface_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_ok.py": "print('hi')\n",
                "Makefile": "gate:\n\tpython scripts/check_ok.py\n",
            },
            ledger={
                "wired": {"check_ok.py": ".github/workflows/nope.yml"},
                "deleted": {},
            },
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "check_ok.py" in result.stdout

    def test_ledger_deleted_row_for_existing_script_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {"scripts/check_ok.py": "print('hi')\n"},
            ledger={
                "wired": {},
                "deleted": {"check_ok.py": "was one-shot"},
            },
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "check_ok.py" in result.stdout

    def test_untriaged_script_with_no_ledger_row_bites(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                "scripts/check_ok.py": "print('hi')\n",
                "Makefile": "gate:\n\tpython scripts/check_ok.py\n",
            },
            ledger={"wired": {}, "deleted": {}},
        )
        result = _run_gate("--root", str(repo), "--check")
        assert result.returncode == 1
        assert "ledger" in result.stdout or "untriaged" in result.stdout
