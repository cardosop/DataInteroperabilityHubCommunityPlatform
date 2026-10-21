"""
W12.8 (oss-release-remediation) — wave-command doc-claim veracity pins.

The named liars: the Wave 2/4/5 batch dispatchers' docstrings claimed
"a re-run of the command never re-emails the same admins".  The real
guard is SEQUENTIAL and WINDOW-SCOPED — the ``--idempotency-days``
audit-row lookback (default 30) — and it is NOT a concurrency or crash
guard: the check and the guard-row write are separate steps (the
send-then-mark order is itself a documented self-heal invariant — an
all-failed batch leaves no row so a retry can self-heal), so two
simultaneous invocations, or a crash between a successful dispatch and
the guard-row write, can double-send, and a re-run after the window
expires re-emails by design.

Each docstring now states that exact contract.  These pins assert the
corrected text is present and the overstatement is gone (the behaviors
themselves are pinned by the existing wave suites — sequential skip,
--force, window expiry, all-failed self-heal).

RED phase: before the fix, all three claims carried "never re-emails"
with no window/concurrency qualifier.
"""

from __future__ import annotations

import re
from pathlib import Path

_COMMANDS = (
    Path(__file__).resolve().parents[2] / "contracts" / "management" / "commands"
)

_CASES = {
    "wave2_send_schema_editor_available_notifications.py": (
        "SCHEMA_EDITOR_AVAILABLE_NOTIFIED"
    ),
    "wave4_send_residue_reminders.py": ("SCHEMA_EDITOR_RESIDUE_REMINDED"),
    "wave5_send_final_warning_notifications.py": (
        "ASSET_AUTO_REVERT_WARNING_NOTIFIED"
    ),
}


def _docstring(filename: str) -> str:
    source = (_COMMANDS / filename).read_text(encoding="utf-8")
    match = re.search(r'"""(.*?)"""', source, re.S)
    assert match, f"{filename}: module docstring missing"
    return match.group(1)


def test_wave_docstrings_carry_the_window_scoped_contract():
    """Every wave dispatcher's idempotency bullet must name the window
    (--idempotency-days) and the sequential scope."""
    for filename, action in _CASES.items():
        doc = _docstring(filename)
        assert "--idempotency-days" in doc or "idempotency-days" in doc, (
            f"{filename}: the idempotency bullet must name the "
            f"--idempotency-days window that scopes the {action} lookback"
        )
        assert "sequential" in doc.lower(), (
            f"{filename}: the bullet must state the guard is sequential, "
            f"not a concurrency/crash guard"
        )


def test_wave_docstrings_disclaim_concurrency_and_crash_safety():
    """The overstatement 'never re-emails' is gone; each docstring must
    state the real failure modes (double-send on simultaneous runs or a
    crash between dispatch and the guard-row write; re-email after the
    window)."""
    for filename, action in _CASES.items():
        doc = _docstring(filename)
        assert "never re-emails" not in doc, (
            f"{filename}: the overstatement must be gone — the guard is "
            f"window-scoped and non-atomic"
        )
        assert "crash" in doc.lower(), (
            f"{filename}: the bullet must name the crash window between "
            f"a successful dispatch and the {action} guard-row write"
        )
        assert "double-send" in doc, (
            f"{filename}: the bullet must name the double-send failure "
            f"mode the non-atomic check+write admits"
        )


def test_wave_docstrings_keep_the_self_heal_invariant():
    """The documented sub-invariant (audit row only when an admin
    actually got the email — all-failed batches self-heal) must stay:
    the corrected claims must not have traded it away."""
    for filename in _CASES:
        doc = _docstring(filename)
        assert "self-heal" in doc, (
            f"{filename}: the send-then-mark self-heal invariant must "
            f"remain documented"
        )
