"""U.8 — go/no-go gate evaluation-logic tests (TDD, no mocks).

Every test exercises the REAL parsing/classification functions in
``scripts/check_go_nogo.py`` against real repo artifacts (the migration
safety policy, the beta-ops runbook, real rehearsal-log shapes) plus
synthetic VIOLATING inputs as falsifiability drills (a fabricated failing
rehearsal log must flip the verdict — the gate exists to say NO).

The slow live evidence battery (smoke, rehearsal, a11y run) is NOT
executed here — those are the gate's own runtime. This suite pins the
EVALUATION logic so a broken parser cannot fake a GO.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_go_nogo as gate

POLICY = REPO_ROOT / "docs" / "operations" / "migration-safety-policy.md"
RUNBOOK = REPO_ROOT / "docs" / "operations" / "beta-ops-runbook.md"


# ── Sign-off ledger parsing ──────────────────────────────────────────────────


def test_signoff_ledger_parses_confirmed_rows():
    rows = gate.parse_signoff_ledger_text(
        "| key | criterion | owner | confirmed | date |\n"
        "|---|---|---|---|---|\n"
        "| oncall-confirmed | Alerting + on-call | admin | yes | 2026-09-03 |\n"
        "| freeze-agreed | Freeze window | admin | no | — |\n"
    )
    assert rows["oncall-confirmed"]["confirmed"] is True
    assert rows["freeze-agreed"]["confirmed"] is False


def test_signoff_ledger_missing_file_is_all_unconfirmed():
    rows = gate.load_signoff_ledger(REPO_ROOT / "docs" / "no-such-ledger.md")
    assert rows == {}


# ── Rehearsal approval parsing (the veto's recorded justifications) ──────────


def test_parse_rehearsal_approvals_extracts_op_ids_from_policy():
    ops = gate.parse_rehearsal_approvals(POLICY)
    # The three recorded approvals (U.7) — the gate refuses to run the
    # rehearsal blind; a missing approval row must change this list.
    assert len(ops) == 3
    assert any(op.startswith("core.0005_remove_eventoutbox") for op in ops)
    assert any(op.startswith("tenants.0097_fix_notification_opt_outs") for op in ops)
    assert any(op.startswith("scheduled_ingestion.0005_remove_ingestiontemplate") for op in ops)


# ── Rehearsal log classification ─────────────────────────────────────────────

_PASS_LOG = """\
[rehearsal] Stage 4/7 — data-loss veto drill (discovered DeleteModel ops)
[rehearsal] [OK]    Stage 4 veto drill complete — every discovered DeleteModel examined
[rehearsal] Stage 6/7 — idempotence (makemigrations --check + migrate --check)
[rehearsal] [OK]    makemigrations --check: no drift
[rehearsal] [OK]    migrate --check: nothing pending
[rehearsal]   Migration rehearsal: ALL STAGES PASSED (dataset: synthetic-E2E)
"""


def test_rehearsal_log_pass_classifies_go():
    result = gate.classify_rehearsal_log(_PASS_LOG)
    assert result.verdict == "PASS"


def test_rehearsal_log_failing_drill_flips_to_fail():
    """Falsifiability drill: a veto-blocked rehearsal must read NO-GO."""
    failing = _PASS_LOG.replace(
        "Stage 4 veto drill complete",
        "DATA-LOSS VETO: 3 DeleteModel op(s) unapproved — the rehearsal is BLOCKING",
    )
    result = gate.classify_rehearsal_log(failing)
    assert result.verdict == "FAIL"
    assert "unapproved" in result.detail


def test_rehearsal_log_missing_all_stages_marker_fails():
    result = gate.classify_rehearsal_log("[rehearsal] Stage 2/7 — migrate forward from zero")
    assert result.verdict == "FAIL"


# ── EKS ticket annotation ────────────────────────────────────────────────────


def test_eks_ticket_annotation_detects_owner_and_expiry():
    assert gate.check_eks_ticket_annotation(
        "ticket 210.29 annotated owner `admin`, EXPIRES 2026-09-30"
    )
    assert not gate.check_eks_ticket_annotation(
        "ticket 210.29 filed — owner TBD"  # no EXPIRES → the go decision cannot pass
    )


# ── a11y ledger cross-check ──────────────────────────────────────────────────


def test_a11y_no_failures_is_pass():
    result = gate.classify_a11y(failed=0, ledgered=0)
    assert result.verdict == "PASS"


def test_a11y_ledgered_failures_are_conditional():
    """Known failures WITH ticket+expiry are LEDGERED — reported, not fake-green."""
    result = gate.classify_a11y(failed=4, ledgered=4)
    assert result.verdict == "LEDGERED"


def test_a11y_unledgered_failures_fail():
    result = gate.classify_a11y(failed=4, ledgered=3)
    assert result.verdict == "FAIL"


def test_parse_a11y_ledger_counts_rows():
    rows = gate.parse_a11y_ledger(REPO_ROOT / "docs" / "operations" / "beta-go-nogo-ledger.md")
    assert len(rows) >= 1
    for row in rows:
        assert row["ticket"].startswith("TICKET=")
        assert re.match(r"\d{4}-\d{2}-\d{2}", row["expires"])


# ── Exit-code mapping ────────────────────────────────────────────────────────


def test_exit_code_all_pass_is_go():
    results = {"a": gate.Result("PASS", ""), "b": gate.Result("PASS", "")}
    assert gate.verdict_exit_code(results) == 0


def test_exit_code_any_fail_is_no_go():
    results = {
        "a": gate.Result("PASS", ""),
        "b": gate.Result("FAIL", "red"),
        "c": gate.Result("LEDGERED", "ticketed"),
    }
    assert gate.verdict_exit_code(results) == 2


def test_exit_code_ledgered_plus_owner_is_awaiting_owner():
    results = {
        "a": gate.Result("PASS", ""),
        "b": gate.Result("LEDGERED", "ticketed"),
        "c": gate.Result("OWNER", "human sign-off pending"),
    }
    assert gate.verdict_exit_code(results) == 4


def test_exit_code_all_green_including_owner_confirmations_is_go():
    results = {
        "a": gate.Result("PASS", ""),
        "b": gate.Result("PASS", "owner confirmed in ledger"),
    }
    assert gate.verdict_exit_code(results) == 0
