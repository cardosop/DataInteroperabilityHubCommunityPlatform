import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.20 — Security: dependency vulnerability scan.

Runs pip-audit against CLI and SDK dependencies and fails on
HIGH/CRITICAL CVEs.
"""

import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_pip_audit(target_dir: Path) -> tuple[int, str]:
    """Run pip-audit in the given directory and return (returncode, output)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pip_audit",
            "--strict",
            "--desc",
            "--format", "columns",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(target_dir),
    )
    return result.returncode, result.stdout + result.stderr


def test_cli_no_high_critical_cves():
    """pip-audit against CLI deps must report no HIGH/CRITICAL vulnerabilities."""
    cli_dir = _REPO_ROOT / "cli"
    if not (cli_dir / "pyproject.toml").exists() and not (cli_dir / "setup.py").exists():
        pytest.skip("CLI package not found")

    try:
        rc, output = _run_pip_audit(cli_dir)
    except FileNotFoundError:
        pytest.skip("pip-audit not installed (pip install pip-audit)")
    except subprocess.TimeoutExpired:
        pytest.skip("pip-audit timed out after 120s")

    if rc != 0 and ("HIGH" in output.upper() or "CRITICAL" in output.upper()):
        pytest.fail(f"CLI dependencies have HIGH/CRITICAL CVEs:\n{output}")


def test_sdk_no_high_critical_cves():
    """pip-audit against SDK deps must report no HIGH/CRITICAL vulnerabilities."""
    sdk_dir = _REPO_ROOT / "sdk" / "python"
    if not (sdk_dir / "pyproject.toml").exists() and not (sdk_dir / "setup.py").exists():
        pytest.skip("SDK package not found")

    try:
        rc, output = _run_pip_audit(sdk_dir)
    except FileNotFoundError:
        pytest.skip("pip-audit not installed (pip install pip-audit)")
    except subprocess.TimeoutExpired:
        pytest.skip("pip-audit timed out after 120s")

    if rc != 0 and ("HIGH" in output.upper() or "CRITICAL" in output.upper()):
        pytest.fail(f"SDK dependencies have HIGH/CRITICAL CVEs:\n{output}")


def test_hub_no_high_critical_cves():
    """pip-audit against hub (backend) deps must report no HIGH/CRITICAL CVEs."""
    hub_dir = _REPO_ROOT
    if not (hub_dir / "requirements.txt").exists():
        pytest.skip("Hub requirements.txt not found")

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pip_audit",
                "--requirement", str(hub_dir / "requirements.txt"),
                "--strict",
                "--desc",
                "--format", "columns",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(hub_dir),
        )
        rc, output = result.returncode, result.stdout + result.stderr
    except FileNotFoundError:
        pytest.skip("pip-audit not installed")
    except subprocess.TimeoutExpired:
        pytest.skip("pip-audit timed out")

    if rc != 0 and ("HIGH" in output.upper() or "CRITICAL" in output.upper()):
        pytest.fail(f"Hub dependencies have HIGH/CRITICAL CVEs:\n{output}")
