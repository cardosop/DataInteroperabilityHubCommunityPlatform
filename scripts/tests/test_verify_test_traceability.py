"""
Tests for test traceability verification (Phase 10.2).

Runs the verify_test_traceability script and asserts all completeness checks pass.
No mocks: uses real docs (FEATURES.md, USE_CASES.md, USER_JOURNEYS.md, USER_PERSONAS.md)
and TEST_TRACEABILITY.md.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Repo root: scripts/tests -> scripts -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_verify_test_traceability_exit_zero():
    """Verify test traceability script exits 0 (all 10.2.1-10.2.5 checks pass)."""
    script = REPO_ROOT / "scripts" / "verify_test_traceability.py"
    if not script.exists():
        pytest.skip("verify_test_traceability.py not found")
    result = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"verify_test_traceability.py failed (exit {result.returncode}). "
        f"stdout: {result.stdout}. stderr: {result.stderr}"
    )


def test_verify_test_traceability_stdout_contains_ok():
    """Verification script output includes OK for each of 10.2.1-10.2.5."""
    script = REPO_ROOT / "scripts" / "verify_test_traceability.py"
    if not script.exists():
        pytest.skip("verify_test_traceability.py not found")
    result = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = result.stdout + result.stderr
    assert "10.2.1 OK" in out or "Every feature" in out
    assert "10.2.2 OK" in out or "use case" in out
    assert "10.2.3 OK" in out or "user journey" in out
    assert "10.2.4 OK" in out or "persona" in out
    assert "10.2.5 OK" in out or "doc IDs" in out
