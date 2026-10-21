"""Phase 232.7 retention auto-enforcer — DB-backed behavioural tests."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_evt
from hub.apps.audit.models import AuditEvent
from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus
from hub.apps.governance.models import RetentionAction, RetentionPolicy, RetentionPolicyType
from hub.apps.governance.retention_auto_enforcer import (
    RetentionAutoEnforcerSweep,
    quarterly_retention_compliance_snapshot,
    retention_enforcement_dashboard,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.tasks_base import _execute_job_logic
from hub.apps.regulation_policies.registry import data_retention_period_days_for_regime_keys
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class Phase232RetentionAutoEnforcerTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"rtn-{uid}",
            slug=f"rtn-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_retention_enforcer_enabled=True,
        )

        self.user = User.objects.create_user(
            email=f"rtn-{uid}@example.com",
            password="pass123456",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"a-{uid}",
            name="Under test",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_regulation_keys_set_retention_via_model_clean(self):
        rp = RetentionPolicy(
            tenant=self.tenant,
            name="Regime driven",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=1,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
            regulation_keys=["GDPR", "CCPA"],
        )
        rp.full_clean()
        rp.save()
        rp.refresh_from_db()
        self.assertEqual(
            rp.retention_period_days,
            data_retention_period_days_for_regime_keys(["GDPR", "CCPA"]),
        )

    @pytest.mark.integration
    def test_enforce_skips_active_legal_hold(self):
        past = timezone.now() - timedelta(days=400)
        Asset.objects.filter(pk=self.asset.pk).update(created_at=past)

        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="hold",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
            legal_hold=True,
            legal_hold_reason="Matter #1",
        )
        with tenant_context(str(self.tenant.id)):
            outcome = RetentionAutoEnforcerSweep.enforce_policy_row(policy, dry_run=False)

        self.assertEqual(outcome["detail"], "legal_hold_active")

    @pytest.mark.integration
    def test_skip_open_dsar_restriction_matching_asset(self):
        past = timezone.now() - timedelta(days=400)
        Asset.objects.filter(pk=self.asset.pk).update(created_at=past)

        DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.RESTRICTION,
            status=DSARStatus.UNDER_REVIEW,
            regimes=["GDPR"],
            subject_email=f"b-{uuid.uuid4().hex[:8]}@example.com",
            details_json={
                "retention_block_scope": {"asset_id": str(self.asset.id)},
            },
        )

        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="dsar block",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
        )
        with tenant_context(str(self.tenant.id)):
            outcome = RetentionAutoEnforcerSweep.enforce_policy_row(policy, dry_run=False)

        self.assertEqual(outcome["detail"], "open_dsar_restriction")

    @pytest.mark.integration
    def test_tombstones_expired_resource_and_schedules_hard_delete(self):
        past = timezone.now() - timedelta(days=400)
        Asset.objects.filter(pk=self.asset.pk).update(created_at=past)
        # ``Asset.objects.filter(...).update(...)`` writes the column
        # directly but doesn't refresh ``self.asset`` (still the
        # original instance with the setUp-time ``created_at``).
        # ``enforce_policy_row`` reads ``policy.asset.created_at``
        # via the cached FK descriptor; without the refresh the
        # enforcer sees ``now()`` and reports
        # ``inside_retention_window`` instead of ``resource_tombstoned``.
        self.asset.refresh_from_db()

        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="expire me",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
        )
        with tenant_context(str(self.tenant.id)):
            outcome = RetentionAutoEnforcerSweep.enforce_policy_row(policy, dry_run=False)

        self.assertEqual(outcome["detail"], "resource_tombstoned")
        policy.refresh_from_db()
        self.assertIsNotNone(policy.tombstoned_at)
        self.assertIsNotNone(policy.hard_delete_scheduled_at)
        # ``Asset`` has no ``deleted_at`` column — its terminal
        # tombstone state is ``status=RETIRED`` (the only "deleted"
        # value the ``asset_status_valid`` CHECK constraint admits).
        # The retention enforcer's ``_soft_delete_resource`` flips
        # status when no ``deleted_at`` is available; assert that
        # transition rather than the missing column.
        asset = Asset.objects.get(pk=self.asset.pk)
        from hub.apps.assets.models import AssetStatus

        self.assertEqual(asset.status, AssetStatus.RETIRED)

    @pytest.mark.integration
    def test_hard_delete_runs_when_grace_deadline_passed(self):
        past = timezone.now() - timedelta(days=800)
        Asset.objects.filter(pk=self.asset.pk).update(created_at=past)

        policy = RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="hard-delete",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
            tombstoned_at=timezone.now() - timedelta(days=100),
            hard_delete_scheduled_at=timezone.now() - timedelta(days=1),
        )
        pk = policy.pk

        with tenant_context(str(self.tenant.id)):
            outcome = RetentionAutoEnforcerSweep.enforce_policy_row(policy, dry_run=False)

        self.assertEqual(outcome["detail"], "hard_deleted_resource")
        self.assertFalse(RetentionPolicy.objects.filter(pk=pk).exists())
        self.assertFalse(Asset.objects.filter(pk=self.asset.pk).exists())

        ev = AuditEvent.objects.filter(
            action=audit_evt.RETENTION_RESOURCE_HARD_DELETED_AUTOSWEEP
        ).exists()
        self.assertTrue(ev)

    @pytest.mark.integration
    def test_quarterly_report_counts_audits(self):
        # ``AuditEvent.timestamp`` has ``auto_now_add=True`` — passing
        # ``timestamp=...`` to ``.create()`` is silently ignored and
        # the row lands at NOW (which is Q2 2026 here, missing the
        # Q1 filter). Backdate via ``.update()`` so the row's
        # timestamp actually falls inside the quarter under test.
        ev = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="RETENTION_POLICY",
            resource_id=uuid.uuid4(),
            action=audit_evt.RETENTION_RESOURCE_TOMBSTONED,
            details_json={"k": "v"},
        )
        AuditEvent.objects.filter(pk=ev.pk).update(
            timestamp=datetime(2026, 2, 10, tzinfo=UTC),
        )

        snapshot = quarterly_retention_compliance_snapshot(
            tenant_id=str(self.tenant.id), year=2026, quarter=1
        )
        self.assertEqual(snapshot["tombstone_events_in_quarter"], 1)

    @pytest.mark.integration
    def test_dashboard_reflects_pending_tombstones(self):
        past = timezone.now() - timedelta(days=400)
        Asset.objects.filter(pk=self.asset.pk).update(created_at=past)
        RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="dashboard",
            asset=self.asset,
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=30,
            action=RetentionAction.SOFT_DELETE.value,
            created_by=self.user,
        )

        dash = retention_enforcement_dashboard(tenant_id=str(self.tenant.id))
        self.assertGreaterEqual(dash["awaiting_initial_tombstone"], 1)

    @pytest.mark.integration
    def test_execute_job_logic_retention_sweep_honours_dry_run_payload(self):
        """Router + tasks_governance handler run without RQ (real sweep, dry_run)."""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.RETENTION_ENFORCEMENT_SWEEP,
            status=JobStatus.PENDING,
            resource_type="SYSTEM",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            details_json={"dry_run": True},
        )
        out = _execute_job_logic(job, JobType.RETENTION_ENFORCEMENT_SWEEP)
        self.assertTrue(out.get("success"))
        summary = out.get("summary") or {}
        self.assertTrue(summary.get("dry_run"))
        self.assertIn("tenants_seen", summary)


class RetentionAutosweepDryRunManagementCommandTests(TestCase):
    """Smoke only — ensures CronJob CLI wiring does not regress."""

    @pytest.mark.integration
    def test_command_supports_dry_run(self):
        out = io.StringIO()
        call_command(
            "retention_enforcement_sweep",
            "--dry-run",
            "--skip-job-row",
            stdout=out,
        )
        self.assertIn("Retention autosweep counters", out.getvalue())
