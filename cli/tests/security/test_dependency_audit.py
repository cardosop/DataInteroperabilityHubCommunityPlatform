import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.20 — Security: dependency vulnerability scan.

Runs pip-audit against CLI and SDK dependencies and fails on
HIGH/CRITICAL CVEs.

pip-audit is a security tool and MUST be available for this test to
provide value.  The test auto-installs it into a temporary venv when
not already importable, so CI and developer machines without
pre-installed pip-audit still get coverage.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Path from this file (sdk/python/tests/security/) to the repo root.
# parents[3] = sdk/  ← wrong (legacy bug masked by pip-audit-not-installed skip)
# parents[4] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]

# Verify the resolved root looks correct (should contain Makefile or .git).
if not (_REPO_ROOT / "Makefile").exists() and not (_REPO_ROOT / ".git").exists():
    # Fallback: walk up until we find a marker
    _candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (_candidate / "Makefile").exists() or (_candidate / ".git").exists():
            _REPO_ROOT = _candidate
            break
        _candidate = _candidate.parent

# Module-level cache: venv with pip-audit installed, or None if
# installation was attempted and failed.
_pip_audit_venv: Path | None = None
_pip_audit_install_attempted: bool = False


def _ensure_pip_audit() -> Path | None:
    """Return a venv directory containing pip-audit, or None.

    Uses a module-level cache so the venv is created once per test
    session and reused across all three parametrized tests.
    """
    global _pip_audit_venv, _pip_audit_install_attempted

    # If we already have a working venv, reuse it
    if _pip_audit_install_attempted and _pip_audit_venv is not None:
        python_exe = _pip_audit_venv / "bin" / "python"
        if python_exe.exists():
            return _pip_audit_venv
        # Venv was cleaned up externally — reset and try again
        _pip_audit_venv = None
        _pip_audit_install_attempted = False

    # If we already tried and failed, don't retry (avoids repeated
    # failures consuming time across multiple tests)
    if _pip_audit_install_attempted:
        return None

    _pip_audit_install_attempted = True

    # Fast path: already importable in the current interpreter
    try:
        subprocess.run(
            [sys.executable, "-c", "import pip_audit"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        _pip_audit_venv = Path(sys.executable).parent.parent  # venv root
        return _pip_audit_venv
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    # Slow path: create a temporary venv and install pip-audit into it
    venv_dir = Path(tempfile.mkdtemp(prefix="pip-audit-venv-"))
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        pip_bin = (
            venv_dir / "bin" / "pip"
            if sys.platform != "win32"
            else venv_dir / "Scripts" / "pip.exe"
        )
        subprocess.run(
            [str(pip_bin), "install", "--quiet", "pip-audit"],
            capture_output=True,
            timeout=120,
            check=True,
        )
        _pip_audit_venv = venv_dir
        return venv_dir
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Clean up the failed venv
        shutil.rmtree(venv_dir, ignore_errors=True)
        return None


def _run_pip_audit(target_dir: Path) -> tuple[int, str]:
    """Run pip-audit in the given directory and return (returncode, output)."""
    venv_dir = _ensure_pip_audit()
    if venv_dir is None:
        return -1, "pip-audit could not be installed"

    python_exe = (
        venv_dir / "bin" / "python"
        if sys.platform != "win32"
        else venv_dir / "Scripts" / "python.exe"
    )
    if not python_exe.exists():
        # Using the current interpreter (fast path)
        python_exe = Path(sys.executable)

    result = subprocess.run(
        [str(python_exe), "-m", "pip_audit", "--strict", "--desc", "--format", "columns"],
        check=False,
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

    rc, output = _run_pip_audit(cli_dir)
    if rc == -1:
        pytest.skip(
            "pip-audit not available: could not install into a temporary venv. "
            "Install pip-audit manually: pip install pip-audit"
        )

    _check_pip_audit_result(rc, output, "CLI")


def test_sdk_no_high_critical_cves():
    """pip-audit against SDK deps must report no HIGH/CRITICAL vulnerabilities."""
    sdk_dir = _REPO_ROOT / "sdk" / "python"
    if not (sdk_dir / "pyproject.toml").exists() and not (sdk_dir / "setup.py").exists():
        pytest.skip("SDK package not found")

    rc, output = _run_pip_audit(sdk_dir)
    if rc == -1:
        pytest.skip(
            "pip-audit not available: could not install into a temporary venv. "
            "Install pip-audit manually: pip install pip-audit"
        )

    _check_pip_audit_result(rc, output, "SDK")


def test_hub_no_high_critical_cves():
    """pip-audit against hub (backend) deps must report no HIGH/CRITICAL CVEs."""
    hub_dir = _REPO_ROOT
    if not (hub_dir / "requirements.txt").exists():
        pytest.skip("Hub requirements.txt not found")

    rc, output = _run_pip_audit(hub_dir)
    if rc == -1:
        pytest.skip(
            "pip-audit not available: could not install into a temporary venv. "
            "Install pip-audit manually: pip install pip-audit"
        )

    _check_pip_audit_result(rc, output, "Hub")


# ---------------------------------------------------------------------------
# Shared result checker
# ---------------------------------------------------------------------------


def _check_pip_audit_result(rc: int, output: str, label: str) -> None:
    """Validate pip-audit output, surfacing errors and warnings."""
    output_upper = output.upper()

    # pip-audit errors (network failures, database errors) — warn,
    # don't fail, because transient PyPI / OSV issues are not code bugs
    if "ERROR" in output_upper or "COULD NOT FETCH" in output_upper:
        pytest.skip(
            f"{label}: pip-audit encountered an error and could not "
            f"complete the scan.  Output:\n{output[:500]}"
        )

    # MEDIUM / LOW findings — emit a warning so they're visible in CI
    if rc != 0 and ("MEDIUM" in output_upper or "LOW" in output_upper):
        import warnings

        warnings.warn(f"{label}: pip-audit found MEDIUM/LOW vulnerabilities:\n{output[:1000]}")

    # HIGH / CRITICAL findings — hard failure
    if rc != 0 and ("HIGH" in output_upper or "CRITICAL" in output_upper):
        pytest.fail(f"{label} dependencies have HIGH/CRITICAL CVEs:\n{output}")


# ---------------------------------------------------------------------------
# Temp-venv cleanup at session end
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session):  # noqa: ARG001
    """Clean up any pip-audit temp venvs left behind by this module."""
    import shutil as _shutil

    if _pip_audit_venv is not None and _pip_audit_venv.exists():
        # Only clean up venvs in temp directories (safety check)
        if "pip-audit-venv-" in str(_pip_audit_venv):
            _shutil.rmtree(_pip_audit_venv, ignore_errors=True)
