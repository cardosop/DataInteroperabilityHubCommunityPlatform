"""
Phase 228 (228.0.DoD.8) — soak-status command tests.

The soak-status command reports a structured per-rule status for the
DoD.5 alert rules across the soak window so the operator (or a daily
cron) can verify "no P1 incidents" without manually clicking through
Grafana. The command queries the live audit-event log + the lineage
metrics directly — no Prometheus HTTP scrape required, so the
command runs cleanly against a staging pod even when Prometheus is
out of band.

The report's status code rolls up:

* ``OK`` — all rules quiet across the window.
* ``WARN`` — at least one ``warning`` / ``info`` alert condition
  matched; no critical conditions.
* ``CRITICAL`` — at least one ``critical`` alert condition matched
  → P1 incident, gate fails.

The command exits non-zero when status is CRITICAL so the cron / CI
soak-tracker can branch on the return code.
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase
from django.utils import timezone


def _create_tenant():
    from hub.apps.tenants.models import Tenant
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Soak Co {suffix}", slug=f"soak-{suffix}")


def _run(*flags) -> tuple[str, int, dict]:
    out = StringIO()
    try:
        call_command("lineage_soak_status", *flags, stdout=out)
        rc = 0
    except CommandError:
        rc = 1
    text = out.getvalue()
    json_lines = [ln for ln in text.strip().splitlines() if ln.startswith("{")]
    report = json.loads(json_lines[-1]) if json_lines else {}
    return text, rc, report


@pytest.mark.django_db(transaction=True)
class TestQuietWindowReportsOK(TransactionTestCase):
    """No drift events + no auto-revert events in the window → OK."""

    def test_quiet_window_returns_ok(self):
        # Scope to a fresh tenant so events from sibling tests in the
        # shared test DB cannot contaminate this assertion. Without
        # this scope, the previous class's CRITICAL drift event would
        # leak into this test's window.
        tenant = _create_tenant()
        _, rc, report = _run(f"--tenant={tenant.id}", "--days=7")
        assert rc == 0
        assert report.get("status") == "OK", (
            f"a brand-new tenant in a 7-day window should be OK; "
            f"got status={report.get('status')}; full report={report!r}"
        )
        # The structure carries every rule-name regardless of status.
        rules = {r["rule"] for r in report["rules"]}
        assert "drift" in rules
        assert "edge_writes" in rules
        assert "auto_revert" in rules


@pytest.mark.django_db(transaction=True)
class TestCriticalDriftEventCausesNonZero(TransactionTestCase):
    """A LineageEdge drift signal in the window → CRITICAL exit."""

    def test_drift_audit_event_triggers_critical(self):
        from hub.apps.audit.utils import create_audit_event

        tenant = _create_tenant()
        # Plant an audit event signalling a drift detection in window.
        create_audit_event(
            tenant=tenant,
            resource_type="LINEAGE_EDGE",
            action="LINEAGE_EDGE_DRIFT_DETECTED",
            resource_id=str(uuid.uuid4()),
            details={"phase": "228.0.DoD.8", "delta_pct": 5.2},
        )

        _, rc, report = _run("--days=7")
        assert rc != 0, (
            f"expected non-zero exit on drift event; got rc={rc}, "
            f"report={report!r}"
        )
        assert report["status"] == "CRITICAL"
        drift_rule = next(r for r in report["rules"] if r["rule"] == "drift")
        assert drift_rule["status"] == "CRITICAL"
        assert drift_rule["count"] >= 1


@pytest.mark.django_db(transaction=True)
class TestWindowFlagFiltersOldEvents(TransactionTestCase):
    """Events outside ``--days`` window do NOT count."""

    def test_event_outside_window_is_excluded(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event

        tenant = _create_tenant()
        e = create_audit_event(
            tenant=tenant,
            resource_type="LINEAGE_EDGE",
            action="LINEAGE_EDGE_DRIFT_DETECTED",
            resource_id=str(uuid.uuid4()),
            details={"phase": "228.0.DoD.8"},
        )
        # Backdate beyond the window.
        AuditEvent.all_objects.filter(pk=e.pk).update(
            timestamp=timezone.now() - timedelta(days=30),
        )

        # Scope to this tenant so unrelated tests' audit rows in the
        # shared test DB don't contaminate the assertion. The window
        # logic is what we're pinning, not cross-test isolation.
        # 7-day window → out-of-window event is excluded → OK exit.
        _, rc, report = _run(f"--tenant={tenant.id}", "--days=7")
        assert rc == 0, (
            f"old event must be excluded; got rc={rc} report={report!r}"
        )
        # 60-day window → in-window → CRITICAL.
        _, rc60, report60 = _run(f"--tenant={tenant.id}", "--days=60")
        assert rc60 != 0
        assert report60["status"] == "CRITICAL"


@pytest.mark.django_db(transaction=True)
class TestReportShape(TransactionTestCase):
    """The JSON report carries the canonical keys the runbook
    references (operator parses these by name)."""

    def test_report_has_canonical_keys(self):
        # Scope to a fresh tenant so the report shape assertion isn't
        # gated on the global DB's status — we're pinning *shape*, not
        # *status*.
        tenant = _create_tenant()
        _, _, report = _run(f"--tenant={tenant.id}", "--days=7")
        for key in ("phase", "status", "window_days", "rules", "checked_at"):
            assert key in report, f"report missing key {key!r}: {report!r}"
        # Each rule entry has the per-rule fields.
        for rule in report["rules"]:
            for k in ("rule", "status", "count", "severity"):
                assert k in rule, f"rule entry missing {k!r}: {rule!r}"
