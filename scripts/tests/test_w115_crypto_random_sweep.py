"""W11.5 (oss-release-remediation) — CSPRNG sweep gate pins.

The ``random.*`` gate (``scripts/check_crypto_random.py``) blocks
non-CSPRNG use in token/key contexts across hub/cli/scripts (register
row 18).  These pins keep the gate HONEST — a checker that reports
nothing detects nothing:

* the real tree sweeps clean (0 unallowlisted token-context sites);
* a PLANTED violation flips the gate RED — both the ``import random``
  attribute form and the ``from random import X`` alias form (the
  alias form is the classic checker blind spot);
* benign usage (backoff jitter) stays green — no false positives;
* allowlist anchors are live (dead anchors fail under
  ``--check-anchors``);
* the committed report exists and covers the real inventory;
* the hash-strength audit names the password-hasher finding and the
  Fernet rotation runbook cites the real management command + flags.

Django-free — runs in the CI no-django lint job; also registered in
the falsifiability harness (gate-62-crypto-random) where the
rename-token-keywords mutation proves the blindness pin bites.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_crypto_random.py"
REPORT = REPO_ROOT / "docs" / "audits" / "w115-random-sweep-report.md"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "fernet-key-rotation.md"
AUDIT = REPO_ROOT / "docs" / "audits" / "w115-crypto-audit-2026-10-16.md"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,  # the gate's exit code IS the assertion input
    )


def test_sweep_is_clean_on_the_real_tree():
    proc = _run(["--check-anchors"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 unallowlisted" in proc.stdout


def test_planted_token_context_violation_flips_red(tmp_path):
    (tmp_path / "secrets_module.py").write_text(
        "import random\nAPI_TOKEN = random.randint(0, 2**64)\n",
        encoding="utf-8",
    )
    proc = _run(["--roots", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "VIOLATION" in proc.stdout
    assert "secrets_module.py:2" in proc.stdout


def test_planted_alias_import_violation_flips_red(tmp_path):
    """The `from random import X` alias form must also flip the gate —
    the classic checker blind spot."""
    (tmp_path / "alias_module.py").write_text(
        "from random import randint\n\n\ndef issue_reset_token():\n"
        "    return randint(0, 999999)\n",
        encoding="utf-8",
    )
    proc = _run(["--roots", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "alias_module.py" in proc.stdout


def test_benign_jitter_usage_stays_green(tmp_path):
    (tmp_path / "backoff.py").write_text(
        "import random\n\n\ndef backoff_with_jitter():\n"
        "    delay = random.uniform(0, 1)\n    return delay\n",
        encoding="utf-8",
    )
    proc = _run(["--roots", str(tmp_path)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_report_exists_and_covers_the_real_inventory():
    assert REPORT.is_file(), "the sweep report must be committed"
    text = REPORT.read_text(encoding="utf-8")
    assert "## Inventory" in text
    assert "Token-context sites — 0" in text
    # The real non-test sites must appear (the report is not decoration).
    for marker in (
        "hub/apps/webhooks/service.py:892",
        "hub/apps/core/resilience/backoff.py:38",
        "hub/apps/transformation/services.py:2690",
    ):
        assert marker in text, f"report missing {marker}"


def test_hash_strength_audit_exists_and_names_the_finding():
    assert AUDIT.is_file(), "the W11.5 crypto audit must be committed"
    text = AUDIT.read_text(encoding="utf-8")
    assert "PASSWORD_HASHERS" in text
    assert "PBKDF2" in text
    # The audit must name the MD5-first posture honestly (finding + fix).
    assert "MD5" in text


def test_fernet_rotation_runbook_cites_the_real_command():
    assert RUNBOOK.is_file(), "the Fernet rotation runbook must be committed"
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "rotate_webhook_encryption_key" in text
    for flag in ("--old-key", "--new-key", "--dry-run"):
        assert flag in text, f"runbook missing {flag}"
