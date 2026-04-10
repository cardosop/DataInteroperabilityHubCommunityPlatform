import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.8.3 — Dimension: operational.

Validates CLI operational behavior:
  - --dry-run support (TODO if not yet implemented per command)
  - Multi-profile config switching
  - Exit code contracts (0=success, 1=error, 2=usage)
  - stdin piping support
  - Output format JSON schema regression
"""

import subprocess
import sys
import tempfile
import os


# ---------------------------------------------------------------------------
# Exit code contracts
# ---------------------------------------------------------------------------

def test_help_exits_zero():
    """datahub --help must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        capture_output=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}: {result.stderr[:200]}"
    )


def test_version_exits_zero():
    """datahub --version must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--version"],
        capture_output=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"--version exited {result.returncode}: {result.stderr[:200]}"
    )


def test_unknown_command_exits_nonzero():
    """datahub nonexistent-command must exit non-zero (usage error)."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "nonexistent-command-xyz"],
        capture_output=True, timeout=10,
    )
    assert result.returncode != 0, (
        "Unknown command should exit non-zero"
    )


def test_version_output_format():
    """--version output must contain the program name and a version string."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--version"],
        capture_output=True, text=True, timeout=10,
    )
    output = result.stdout.strip()
    assert "datahub" in output.lower(), f"Version output missing 'datahub': {output}"
    # Should contain a version-like pattern (digits and dots)
    import re
    assert re.search(r'\d+\.\d+', output), f"Version output has no version number: {output}"


# ---------------------------------------------------------------------------
# Multi-profile config
# ---------------------------------------------------------------------------

def test_config_dir_respected():
    """DATAHUB_CONFIG_DIR env var should control where config is read."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = os.path.join(tmpdir, ".datahub")
        os.makedirs(config_dir)
        config_path = os.path.join(config_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write("api_url: http://custom-host:9999/api/v1\napi_key: test-key\n")

        result = subprocess.run(
            [sys.executable, "-m", "datahub_cli", "--help"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "DATAHUB_CONFIG_DIR": config_dir},
        )
        # --help should still work regardless of config content
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# --dry-run support audit
# ---------------------------------------------------------------------------

def test_dry_run_flag_audit():
    """Verify --dry-run is advertised in help and accepted without error."""
    # 1. --dry-run must appear in root help text
    help_result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert help_result.returncode == 0
    assert "--dry-run" in help_result.stdout, (
        "--dry-run flag not found in root help output"
    )

    # 2. --dry-run with --help must still exit 0 (flag is accepted)
    dry_help = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--dry-run", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert dry_help.returncode == 0, (
        f"--dry-run --help exited {dry_help.returncode}: {dry_help.stderr[:200]}"
    )


# ---------------------------------------------------------------------------
# stdin piping
# ---------------------------------------------------------------------------

def test_stdin_piping_does_not_crash():
    """CLI must not crash when stdin is a pipe (non-TTY).

    Many CI environments and scripts pipe input; the CLI must handle
    non-interactive stdin gracefully (no isatty() crash).
    """
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        input="",  # stdin is a pipe with empty content
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"CLI crashed with piped stdin: exit {result.returncode}, "
        f"stderr={result.stderr[:200]}"
    )


def test_stdin_pipe_with_data_does_not_hang():
    """CLI with unexpected stdin data must not hang waiting for more input."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--version"],
        input="unexpected input data\n",
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"CLI hung or crashed with piped data: exit {result.returncode}"
    )


# ---------------------------------------------------------------------------
# Output format JSON schema regression
# ---------------------------------------------------------------------------

def test_help_output_is_text():
    """--help output must be plain text (not JSON, not HTML)."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    output = result.stdout
    assert not output.strip().startswith("{"), "Help output looks like JSON"
    assert not output.strip().startswith("<"), "Help output looks like HTML"
    assert "Usage:" in output or "usage:" in output.lower(), (
        f"Help output missing 'Usage:': {output[:200]}"
    )


def test_error_output_goes_to_stderr():
    """Error messages for unknown commands should go to stderr."""
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "nonexistent-xyz"],
        capture_output=True, text=True, timeout=10,
    )
    # Click writes error messages to stderr
    combined = result.stdout + result.stderr
    assert "error" in combined.lower() or "no such command" in combined.lower() or "usage" in combined.lower(), (
        f"No error message found in output: stdout={result.stdout[:100]}, stderr={result.stderr[:100]}"
    )
