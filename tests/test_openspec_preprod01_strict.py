"""
D231.1 — Mirror gate: ``openspec validate preprod01 --strict`` MUST succeed.

Runs the real OpenSpec CLI via subprocess (no stubs): prefers ``openspec`` on
``PATH``, otherwise the same pinned ``npx --yes @fission-ai/openspec@1.3.1``
invocation as ``.github/workflows/ci.yml`` (lint job). Skips only when neither
is available.

Invoking **only** this file (the default CI/local pattern) sets
``OPEN_SPEC_PREPROD01_GATE_ONLY=1`` via ``tests/conftest.py::pytest_configure``
so the suite skips Django session bootstrap. Mixed test runs must set that env
explicitly if this module is collected alongside Django tests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PINNED_OPENSPEC_NPX = (
    "@fission-ai/openspec@1.3.1",
    "validate",
    "preprod01",
    "--strict",
)

pytestmark = pytest.mark.openspec_gate


def _openspec_validate_argv() -> list[str] | None:
    openspec_bin = shutil.which("openspec")
    if openspec_bin:
        return [openspec_bin, "validate", "preprod01", "--strict"]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", *_PINNED_OPENSPEC_NPX]
    return None


@pytest.mark.skipif(
    _openspec_validate_argv() is None,
    reason="needs openspec CLI or npx on PATH",
)
def test_preprod01_strict_validate_exits_zero():
    argv = _openspec_validate_argv()
    assert argv is not None
    env = os.environ.copy()
    env.setdefault("CI", "true")
    env.setdefault("OPENSPEC_TELEMETRY", "0")
    proc = subprocess.run(
        argv,
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, (
        "openspec validate preprod01 --strict failed:\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
