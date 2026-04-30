"""
Phase 227 Wave 4 (227.W4.3) — 30-day escalation command tests.

Pins the cron-driven escalation that fires when a tenant's W4.2
residue reminder deadline has passed.  Behaviours pinned:

* Only tenants with a ``SCHEMA_EDITOR_RESIDUE_REMINDED`` audit row
  whose ``details.deadline`` is past are eligible.
* Tenants whose residue was remediated since the reminder are NOT
  escalated (re-load contracts at run time, not at reminder time).
* Eligible tenants get a ``STRUCTURELESS_RESIDUE_DEADLINE_PASSED``
  audit row.
* Idempotency: re-running the cron does NOT emit duplicate
  escalations for the same (tenant, reminder) pair.
* ``--dry-run`` writes neither audit rows nor platform-admin notifications.
* ``--audit-output`` JSONL artefact for ops verification.

No mocks of internal code; real DB rows for tenants, contracts,
audit events.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone


def _create_tenant(slug_prefix: str = "w43"):
    from hub.apps.tenants.models import Tenant
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
    )


def _create_contract(tenant, *, hub_contract_json):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.DRAFT,
    )


def _record_reminded(tenant, *, deadline: _dt.date, when=None, residue_count: int = 1):
    """Write a SCHEMA_EDITOR_RESIDUE_REMINDED audit row carrying the
    deadline, optionally backdated."""
    from hub.apps.audit.models import AuditEvent
    event = AuditEvent.objects.create(
        tenant=tenant,
        action="SCHEMA_EDITOR_RESIDUE_REMINDED",
        resource_type="TENANT",
        resource_id=tenant.id,
        result="SUCCESS",
        details_json={
            "phase": "227.W4.2",
            "deadline": deadline.isoformat(),
            "residue_count": residue_count,
        },
    )
    if when is not None:
        AuditEvent.all_objects.filter(pk=event.pk).update(timestamp=when)
        event.refresh_from_db()
    return event


_HC_OK = {
    "models": [{"name": "m", "fields": [{"name": "id", "data_type": "string"}]}],
    "schema": {"fields": [{"name": "id", "data_type": "string"}]},
}
_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


# ---------------------------------------------------------------------------
# Eligibility filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class EscalationEligibilityTests(TestCase):

    def test_tenant_past_deadline_with_residue_is_escalated(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("past-deadline")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        call_command("wave4_escalate_residue", stdout=io.StringIO())

        rows = AuditEvent.objects.filter(
            tenant=tenant,
            action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
        )
        self.assertEqual(rows.count(), 1)

    def test_tenant_with_future_deadline_is_not_escalated(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("future-deadline")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant,
            deadline=_dt.date.today() + timedelta(days=10),
        )

        call_command("wave4_escalate_residue", stdout=io.StringIO())

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            0,
        )

    def test_remediated_tenant_is_not_escalated(self):
        """The cron must verify residue is STILL present at run time —
        a tenant who fixed their contracts the day before the deadline
        deserves a quiet exit, not an escalation."""
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("remediated")
        _create_contract(tenant, hub_contract_json=_HC_OK)  # already clean
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        call_command("wave4_escalate_residue", stdout=io.StringIO())

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            0,
        )

    def test_tenant_with_no_reminder_audit_row_is_not_escalated(self):
        """Defensive: a tenant the cron knows nothing about (never
        reminded) must NOT be escalated.  The cron's only valid
        input is the W4.2 audit-row history."""
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("never-reminded")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)

        call_command("wave4_escalate_residue", stdout=io.StringIO())

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            0,
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class EscalationIdempotencyTests(TestCase):

    def test_re_running_does_not_double_escalate(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("idem-esc")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        # Run twice.
        call_command("wave4_escalate_residue", stdout=io.StringIO())
        call_command("wave4_escalate_residue", stdout=io.StringIO())

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            1,
            "Re-running the cron must NOT double-escalate; "
            "the second run should detect the existing "
            "STRUCTURELESS_RESIDUE_DEADLINE_PASSED row.",
        )


# ---------------------------------------------------------------------------
# Output / dry-run
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class EscalationActiveOnlyScopeTests(TestCase):
    """W4.2/W4.3-AUDIT-1 regression — ``--include-active-only`` on the
    cron matches the W4.2 reminder + W4.4 smoke-gate scope so a tenant
    whose only residue is DRAFT (data-engineer's edit buffer) doesn't
    get the ``STRUCTURELESS_RESIDUE_DEADLINE_PASSED`` audit row."""

    def test_active_only_treats_draft_residue_as_remediated(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            OriginalFormat,
            OriginalSpecType,
        )

        tenant = _create_tenant("draft-only-esc")
        Contract.objects.create(
            tenant=tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json=_HC_STRUCTURELESS,
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.DRAFT,
        )
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        out = io.StringIO()
        call_command(
            "wave4_escalate_residue",
            "--include-active-only",
            stdout=out,
        )

        # Under --include-active-only the DRAFT residue contract
        # doesn't keep the tenant in the escalation cohort: the cron
        # records this as ``remediated``, NOT ``escalate``.
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            0,
        )
        self.assertIn("[remediated]", out.getvalue())

    def test_active_only_still_escalates_active_residue(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            OriginalFormat,
            OriginalSpecType,
        )

        tenant = _create_tenant("active-residue-esc")
        Contract.objects.create(
            tenant=tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json=_HC_STRUCTURELESS,
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.ACTIVE,
        )
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        call_command(
            "wave4_escalate_residue",
            "--include-active-only",
            stdout=io.StringIO(),
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            1,
        )


@pytest.mark.django_db(transaction=True)
class EscalationOutputTests(TestCase):

    def test_dry_run_writes_no_audit_rows(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("dry-esc")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        out = io.StringIO()
        call_command(
            "wave4_escalate_residue", "--dry-run", stdout=out,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=tenant,
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
            ).count(),
            0,
        )
        self.assertIn("[dry-run]", out.getvalue())

    def test_audit_output_jsonl(self):
        tenant = _create_tenant("audit-esc")
        _create_contract(tenant, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
            residue_count=2,
        )

        tmpdir = Path(tempfile.mkdtemp())
        path = tmpdir / "wave4-esc.jsonl"
        call_command(
            "wave4_escalate_residue",
            f"--audit-output={path}",
            stdout=io.StringIO(),
        )

        self.assertTrue(path.exists())
        rows = [
            json.loads(line)
            for line in path.read_text().splitlines() if line.strip()
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tenant_id"], str(tenant.id))
        self.assertIn("deadline", rows[0])
        self.assertIn("residue_count", rows[0])

    def test_summary_line_reports_cohort_counts(self):
        tenant_esc = _create_tenant("summary-esc")
        _create_contract(tenant_esc, hub_contract_json=_HC_STRUCTURELESS)
        _record_reminded(
            tenant_esc,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )
        tenant_clean = _create_tenant("summary-clean")
        _create_contract(tenant_clean, hub_contract_json=_HC_OK)
        _record_reminded(
            tenant_clean,
            deadline=_dt.date.today() - timedelta(days=1),
            when=timezone.now() - timedelta(days=31),
        )

        out = io.StringIO()
        call_command("wave4_escalate_residue", stdout=out)
        text = out.getvalue()
        # One escalation, one clean (remediated).
        self.assertIn("escalated=1", text)
        self.assertIn("remediated=1", text)
