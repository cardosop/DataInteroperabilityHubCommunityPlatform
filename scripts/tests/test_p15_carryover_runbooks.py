"""
P0-15 (close-oss-release-conditions) — W10.2 carryover runbook + ledger
items.

Three carryover tickets, each pinned at its weakest point:

1. **W105-REDIS-AOF-RUNBOOK** — the unclean-kill → AOF-tear runbook
   exists and orders the steps correctly: BACKUP FIRST, then
   `redis-check-aof --fix`, and records that redis-queue is
   job-state-only (the hub DB is the truth).
2. **W105-COMPOSE-SUPERVISOR-RESTART** — the observation is recorded in
   the ops runbook AND cited from the W10.2 soak record (the
   acceptance's citation direction).
3. **W105-BILLING-REFUND-LEDGER** — the work is routed to the billing
   lane: the `billing-refund-ledger` change is opened (validator-clean)
   and cited from the backlog row.

No mocks: real files, real validator, real doc-anchor pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS.parent))

from validate_openspec_change import collect_violations

AOF_RUNBOOK = REPO_ROOT / "docs/runbooks/redis-aof-tear-recovery.md"
SUPERVISOR_RUNBOOK = REPO_ROOT / "docs/runbooks/compose-restart-supervisor.md"
SOAK_AUDIT = REPO_ROOT / "docs/audits/w102-staging-soak-2026-10-17.md"
BACKLOG = REPO_ROOT / "openspec/changes/track-oss-deferred-debt/tasks.md"
BILLING_CHANGE = REPO_ROOT / "openspec/changes/billing-refund-ledger"


# ── 1. Redis AOF-tear runbook ─────────────────────────────────────────────


def test_aof_runbook_exists_with_backup_first_order():
    text = AOF_RUNBOOK.read_text(encoding="utf-8")
    assert "redis-check-aof --fix" in text, (
        "the recovery command must be documented"
    )
    backup_idx = text.index("BACKUP")
    fix_idx = text.index("redis-check-aof --fix")
    assert backup_idx < fix_idx, (
        "the backup step must come BEFORE the fix — a --fix on an "
        "unbacked-up AOF destroys the torn tail irreversibly"
    )


def test_aof_runbook_records_db_is_the_truth():
    text = AOF_RUNBOOK.read_text(encoding="utf-8")
    assert "job-state-only" in text, (
        "redis-queue is job-state-only — losing pending jobs is not data loss"
    )
    assert "hub DB is the truth" in text


def test_aof_runbook_cites_the_2026_10_17_case():
    text = AOF_RUNBOOK.read_text(encoding="utf-8")
    assert "170" in text, (
        "the repaired incident (170 crash-loops) must be recorded as "
        "the worked example"
    )
    assert "1004-byte" in text, (
        "the 1004-byte torn tail must be recorded as the worked example"
    )


# ── 2. Compose supervisor observation ────────────────────────────────────


def test_supervisor_observation_recorded_in_runbook():
    text = SUPERVISOR_RUNBOOK.read_text(encoding="utf-8")
    assert "did not fire within 2 min" in text, (
        "the observation must be recorded verbatim-ish"
    )
    assert "k8s" in text or "orchestrator" in text, (
        "production restarts are the orchestrator's job — the record "
        "must state the policy boundary"
    )


def test_supervisor_observation_cited_from_soak_record():
    """The acceptance: the runbook entry is cited FROM the W10.2 ledger
    (the soak audit §4 record)."""
    text = SOAK_AUDIT.read_text(encoding="utf-8")
    assert "docs/runbooks/compose-restart-supervisor.md" in text, (
        "the W10.2 §4 record must cite the runbook entry"
    )


# ── 3. Billing-refund-ledger routing ─────────────────────────────────────


def test_billing_change_opened_and_valid():
    assert BILLING_CHANGE.is_dir(), "the routed change must be opened"
    violations = collect_violations(BILLING_CHANGE)
    assert violations == [], violations


def test_billing_change_proposal_records_the_f3_state():
    proposal = (BILLING_CHANGE / "proposal.md").read_text(encoding="utf-8")
    assert "W10.3 F3" in proposal
    assert "idempotency" in proposal, (
        "the shipped Stripe idempotency key must be recorded as the "
        "completed half"
    )
    assert "race pins" in proposal or "W11.7" in proposal, (
        "the acceptance (race pins under the ledgered path) must be named"
    )


# ── 4. Backlog rows ──────────────────────────────────────────────────────


def test_backlog_rows_closed_with_citations():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "[x] `TICKET=W105-REDIS-AOF-RUNBOOK`" in text, (
        "the AOF runbook ticket closes with its citation"
    )
    assert "[x] `TICKET=W105-COMPOSE-SUPERVISOR-RESTART`" in text, (
        "the supervisor ticket closes with its citation"
    )
    assert "docs/runbooks/redis-aof-tear-recovery.md" in text
    assert "docs/runbooks/compose-restart-supervisor.md" in text


def test_billing_row_routed_to_the_change():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "[ ] `TICKET=W105-BILLING-REFUND-LEDGER`" in text, (
        "the billing work stays open (acceptance = race pins under the "
        "ledgered path — billing-lane execution)"
    )
    row_tail = text.split(
        "- [ ] `TICKET=W105-BILLING-REFUND-LEDGER`", 1
    )[1]
    assert "billing-refund-ledger" in row_tail[:800], (
        "the Phase-1 row must cite the opened routed change"
    )
