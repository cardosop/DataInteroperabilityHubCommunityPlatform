"""P0-17 (close-oss-release-conditions, 1.17 Wave A) — gate pins.

Two tickets, two gates, each RED-first:

W105-SIGNAL-TENANT-CONTEXT-LINT — ``scripts/lint_signal_tenant_context.py``:
every signal receiver registered under hub/apps (``@receiver`` decorator
or ``<signal>.connect(...)``) must wrap its body in ``tenant_context``
(evidence: a ``tenant_context`` / ``_run_with_tenant_context`` /
``run_with_tenant_context`` call in the receiver body). Unwrapped
receivers flip the gate RED; the YAML allowlist is the only escape and
is ratcheted. A NEW unwrapped receiver cannot land silently.

W105-MGMT-COMMAND-AUDIT — ``scripts/check_mgmt_command_audit.py``:
every management command under hub is either audited (static evidence:
the ``AuditedCommand`` base / ``emit_command_audit`` / a
``create_audit_event`` call in the command module) or read-only
allowlisted (``lint/mgmt-command-audit-allowlist.yml``, path:reason).
A NEW unwired command flips the gate RED.

No mocks: real files scanned by the real gates; planted fixtures are
real Python modules with real AST shape.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
SIGNAL_GATE = REPO_ROOT / "scripts/lint_signal_tenant_context.py"
CMD_GATE = REPO_ROOT / "scripts/check_mgmt_command_audit.py"


def _run(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _plant(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── W105-SIGNAL-TENANT-CONTEXT-LINT ──────────────────────────────────────────


def test_signal_gate_flags_unwrapped_receiver(tmp_path):
    _plant(
        tmp_path / "app/signals.py",
        "from django.db.models.signals import post_save\n"
        "from django.dispatch import receiver\n\n"
        "@receiver(post_save, sender='assets.Asset')\n"
        "def rebuild_search(sender, instance, **kwargs):\n"
        "    instance.search_vector = 'x'\n"
        "    instance.save()\n",
    )
    proc = _run(SIGNAL_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(tmp_path / "allow.yml")])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "rebuild_search" in (proc.stdout + proc.stderr)


def test_signal_gate_accepts_wrapped_receiver(tmp_path):
    _plant(
        tmp_path / "app/signals.py",
        "from django.db.models.signals import post_save\n"
        "from django.dispatch import receiver\n\n"
        "@receiver(post_save, sender='assets.Asset')\n"
        "def rebuild_search(sender, instance, **kwargs):\n"
        "    from hub.apps.tenants.request_tenant import tenant_context\n"
        "    with tenant_context(getattr(instance, 'tenant_id', None)):\n"
        "        instance.search_vector = 'x'\n"
        "        instance.save()\n",
    )
    proc = _run(SIGNAL_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(tmp_path / "allow.yml")])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_signal_gate_accepts_helper_wrap_evidence(tmp_path):
    _plant(
        tmp_path / "app/signals.py",
        "from django.db.models.signals import post_save\n"
        "from django.dispatch import receiver\n\n"
        "@receiver(post_save, sender='assets.Asset')\n"
        "def rebuild_search(sender, instance, **kwargs):\n"
        "    _run_with_tenant_context(getattr(instance, 'tenant_id', None), lambda: None)\n",
    )
    proc = _run(SIGNAL_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(tmp_path / "allow.yml")])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_signal_gate_allowlist_escape(tmp_path):
    _plant(
        tmp_path / "app/signals.py",
        "from django.db.models.signals import post_save\n"
        "from django.dispatch import receiver\n\n"
        "@receiver(post_save, sender='assets.Asset')\n"
        "def rebuild_search(sender, instance, **kwargs):\n"
        "    instance.search_vector = 'x'\n"
        "    instance.save()\n",
    )
    allow = tmp_path / "allow.yml"
    _plant(
        allow,
        f"- path: \"{tmp_path / 'app/signals.py'}\"\n"
        "  line: 5\n"
        "  reason: \"fixture exemption\"\n",
    )
    proc = _run(SIGNAL_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(allow)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_signal_gate_green_on_real_tree():
    proc = _run(SIGNAL_GATE, [])
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── W105-MGMT-COMMAND-AUDIT ──────────────────────────────────────────────────


def test_cmd_gate_flags_unwired_command(tmp_path):
    _plant(
        tmp_path / "app/management/commands/do_thing.py",
        "from django.core.management.base import BaseCommand\n\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        print('mutating tenant data')\n",
    )
    proc = _run(CMD_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(tmp_path / "allow.yml")])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "do_thing" in (proc.stdout + proc.stderr)


def test_cmd_gate_accepts_audited_command(tmp_path):
    _plant(
        tmp_path / "app/management/commands/do_thing.py",
        "from hub.apps.audit.command_audit import AuditedCommand\n\n"
        "class Command(AuditedCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        print('audited')\n",
    )
    proc = _run(CMD_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(tmp_path / "allow.yml")])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cmd_gate_allowlist_escape(tmp_path):
    _plant(
        tmp_path / "app/management/commands/wait_for_thing.py",
        "from django.core.management.base import BaseCommand\n\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        print('read-only probe')\n",
    )
    allow = tmp_path / "allow.yml"
    _plant(
        allow,
        f"- path: \"{tmp_path / 'app/management/commands/wait_for_thing.py'}\"\n"
        "  reason: \"read-only readiness probe\"\n",
    )
    proc = _run(CMD_GATE, ["--path", str(tmp_path / "app"), "--allowlist", str(allow)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cmd_gate_green_on_real_tree():
    proc = _run(CMD_GATE, [])
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── Wiring ───────────────────────────────────────────────────────────────────


def test_gates_ci_wired():
    lint_yml = (REPO_ROOT / ".github/workflows/_reusable.lint.yml").read_text(encoding="utf-8")
    ci_yml = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/tests/test_p17_wave_a_gates.py" in lint_yml, (
        "P0-17 pins must be CI-wired in the lint list"
    )
    for gate in ("lint_signal_tenant_context.py", "check_mgmt_command_audit.py"):
        assert gate in ci_yml, f"{gate} must be wired into CI (dedicated job)"
