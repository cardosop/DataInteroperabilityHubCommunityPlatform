"""W10.2 (oss-release-remediation) — the test-mode detector must not fire
in production.  (The test-mode branch itself is exercised by every
existing suite — thousands of tests run with the branch active — so only
the PRODUCTION-shape pins are needed here.)

Live-staging evidence: graphene-django's settings module imports
``django.test`` at app boot, which pulls ``unittest`` into
``sys.modules`` — and the settings' test-mode branches keyed on
``"unittest" in sys.modules`` flipped the STAGING worker into the
TEST-mode webhook config (``WEBHOOK_ASYNC_DELIVERY=False``, the inline
synchronous delivery path, ``WEBHOOK_DELIVERY_MAX_RETRIES=2``).

The detector must key on REAL test-run signals only (pytest presence,
PYTEST_CURRENT_TEST, the TESTING env, or ``test`` in argv) — never on
the mere presence of ``unittest`` in ``sys.modules``.

Pins run settings in a REAL subprocess (the production shape: a
third-party library has already imported ``unittest``) — no mocks.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _boot(
    extra_imports: str, argv_note: str, with_test_argv: bool = False
) -> subprocess.CompletedProcess:
    code = (
        "import os, sys\n"
        f"{extra_imports}\n"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')\n"
        "import django; django.setup()\n"
        "from django.conf import settings\n"
        "print('ASYNC=' + str(getattr(settings, 'WEBHOOK_ASYNC_DELIVERY', 'MISSING')))\n"
        "print('SYNCPERSIST=' + str(getattr(settings, 'EVENT_BUS_FORCE_SYNC_PERSISTENCE', 'MISSING')))\n"
        f"print('ARGVNOTE={argv_note}')\n"
    )
    argv = [sys.executable, "-c", code] + (["test"] if with_test_argv else [])
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ENVIRONMENT", "TESTING", "PYTEST_CURRENT_TEST")
    }
    env["ENVIRONMENT"] = "development"
    return subprocess.run(
        argv,
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class TestUnittestImportDoesNotFlipTestMode:
    """The production shape: unittest already imported by a third-party
    library, NO test argv — the deployment config must win."""

    def test_async_delivery_stays_true_when_unittest_is_imported(self):
        result = _boot("import unittest\n", "no-test-argv")
        out = result.stdout + result.stderr
        assert "ASYNC=True" in out, out

    def test_sync_persistence_stays_false_when_unittest_is_imported(self):
        result = _boot("import unittest\n", "no-test-argv")
        out = result.stdout + result.stderr
        assert "SYNCPERSIST=False" in out, out

