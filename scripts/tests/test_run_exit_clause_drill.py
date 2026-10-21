"""TDD contract pins for scripts/run_exit_clause_drill.py (pilot-readiness
4.4 exit-clause drill) — the REAL execution is the drill itself; these pins
guard its CLI contract and the Makefile wiring.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRILL = REPO_ROOT / "scripts" / "run_exit_clause_drill.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(DRILL), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestCliContract:
    def test_missing_admin_credentials_exits_2(self):
        result = _run("--skip-seed")
        assert result.returncode == 2, result.stdout
        assert "admin-email" in result.stdout + result.stderr

    def test_docstring_documents_all_seven_stages(self):
        doc = DRILL.read_text().split('"""')[1]
        for stage in (
            "seed",
            "export",
            "soft-delete",
            "guardrails",
            "hard-delete",
            "verify",
            "report",
        ):
            assert stage in doc, f"docstring must document the {stage} stage"

    def test_drill_uses_the_documented_tenant_ids(self):
        text = DRILL.read_text()
        assert '"pilot-exit-drill"' in text
        assert "bbbbbbb1-0001-4001-8001-000000000001" in text

    def test_drill_reports_to_the_runbook_report_dir(self):
        text = DRILL.read_text()
        assert "docs/operations/exit-clause-drill-reports" in text


class TestMakefileWiring:
    def test_make_target_runs_the_real_drill(self):
        makefile = (REPO_ROOT / "Makefile").read_text()
        block = makefile.split("exit-clause-drill:", 1)[1].split("\n\n", 1)[0]
        assert "run_exit_clause_drill.py" in block, "make exit-clause-drill must run the real drill"

    def test_all_four_rehearsal_targets_are_phony(self):
        makefile = (REPO_ROOT / "Makefile").read_text()
        phony = makefile.splitlines()[0]
        for target in ("dr-drill", "tls-rotation-drill", "load-test-week1", "exit-clause-drill"):
            assert target in phony, f"{target} missing from .PHONY"
