"""
Phase 231.1 — Auto-scan signal on Asset registration (intake gate).

Uses real ORM, cache, jobs, and audit rows (no mocks).
"""

from __future__ import annotations
import pytest
import pytest

import uuid
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.compliance.intake_scan import (
    COMPLIANCE_INTAKE_ACTIVATION_BLOCKER,
    enqueue_compliance_intake_scan,
)
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ComplianceIntakeSignalTest(TestCase):
    """231.1 — post_save on Asset enqueues compliance run when gate enabled."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Intake Gate Tenant {uid}",
            slug=f"intake-gate-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_intake_gate_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"intake-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        cache.clear()

    @pytest.mark.integration
    def test_signal_enqueues_compliance_run_when_gate_enabled(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"gate-asset-{uuid.uuid4().hex[:6]}",
            name="Intake Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        runs = ComplianceRun.objects.filter(asset=asset)
        self.assertEqual(runs.count(), 1)

        run = runs.first()
        assert run is not None
        self.assertEqual(run.status, ComplianceRunStatus.PENDING)
        self.assertIsNotNone(run.job)
        self.assertEqual(run.job.type, JobType.COMPLIANCE_RUN)

        ev = AuditEvent.objects.filter(
            action=event_types.COMPLIANCE_INTAKE_SCAN_ENQUEUED,
            tenant_id=self.tenant.id,
        ).first()
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.details_json.get("asset_id"), str(asset.id))
        self.assertEqual(ev.details_json.get("compliance_run_id"), str(run.id))

    @pytest.mark.integration
    def test_signal_silent_when_gate_disabled(self):
        self.tenant.compliance_intake_gate_enabled = False
        self.tenant.save(update_fields=["compliance_intake_gate_enabled"])

        Asset.objects.create(
            tenant=self.tenant,
            key=f"no-gate-{uuid.uuid4().hex[:6]}",
            name="No Gate",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action=event_types.COMPLIANCE_INTAKE_SCAN_ENQUEUED,
            ).exists(),
        )
        self.assertEqual(ComplianceRun.objects.filter(tenant=self.tenant).count(), 0)

    @pytest.mark.integration
    def test_enqueue_idempotency_second_call_skips_within_ttl(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"idemp-{uuid.uuid4().hex[:6]}",
            name="Idemp",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        count_after_signal = ComplianceRun.objects.filter(asset=asset).count()
        self.assertEqual(count_after_signal, 1)

        again = enqueue_compliance_intake_scan(str(asset.id), str(self.tenant.id))
        self.assertIsNone(again)
        self.assertEqual(ComplianceRun.objects.filter(asset=asset).count(), 1)

    @pytest.mark.integration
    def test_can_activate_blocked_when_gate_on_without_succeeded_pass(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"block-{uuid.uuid4().hex[:6]}",
            name="Blocked",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "x"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )

        can, blockers = asset.can_activate()
        self.assertFalse(can)
        self.assertIn(COMPLIANCE_INTAKE_ACTIVATION_BLOCKER, blockers)

    @pytest.mark.integration
    def test_can_activate_passes_when_succeeded_allowed_run_exists(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"ok-{uuid.uuid4().hex[:6]}",
            name="Ok",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "x"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            # Phase 227 structural-floor invariant: an info-only
            # ``hub_contract_json`` (no models / schema fields) trips
            # ``STRUCTURELESS_ODCS_NO_SCHEMA`` and blocks activation
            # before the compliance check this test is exercising
            # ever runs.
            hub_contract_json={
                "info": {"name": "X", "version": "1.0.0"},
                "models": [
                    {
                        "name": "primary",
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False},
                        ],
                    }
                ],
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            },
            created_by=self.user,
        )

        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        from django.utils import timezone

        # Risk level must NOT exceed the tenant threshold (default
        # HIGH); seed LOW so the gate at
        # ``compliance_threshold_activation_blocker`` doesn't refuse.
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level="LOW",
            allowed_to_store=True,
            completed_at=timezone.now(),
        )

        can, blockers = asset.can_activate()
        self.assertTrue(can, msg=blockers)
        self.assertNotIn(COMPLIANCE_INTAKE_ACTIVATION_BLOCKER, blockers)

    @pytest.mark.integration
    def test_intake_gate_blocks_when_latest_run_failed_after_prior_success(self):
        """Latest run wins: older SUCCEEDED must not bypass a newer FAILED."""
        self.tenant.compliance_intake_gate_enabled = False
        self.tenant.save(update_fields=["compliance_intake_gate_enabled"])
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"latest-fail-{uuid.uuid4().hex[:6]}",
            name="Latest Fail",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "x"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )
        self.tenant.compliance_intake_gate_enabled = True
        self.tenant.save(update_fields=["compliance_intake_gate_enabled"])

        from django.utils import timezone

        j_ok = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=j_ok,
            status=ComplianceRunStatus.SUCCEEDED,
            allowed_to_store=True,
            completed_at=timezone.now() - timedelta(hours=1),
        )
        j_fail = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=j_fail,
            status=ComplianceRunStatus.FAILED,
            allowed_to_store=False,
            completed_at=timezone.now(),
        )
        can, blockers = asset.can_activate()
        self.assertFalse(can)
        self.assertIn(COMPLIANCE_INTAKE_ACTIVATION_BLOCKER, blockers)

    @pytest.mark.integration
    def test_activation_emits_gate_block_audit(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"audit-{uuid.uuid4().hex[:6]}",
            name="Audit",
            status=AssetStatus.DRAFT,
            created_by=self.user,
            version=0,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "x"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
            created_by=self.user,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        url = f"/api/v1/assets/{asset.id}/activate/"
        resp = client.post(url, {"version": 0}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        blocked = AuditEvent.objects.filter(
            action=event_types.COMPLIANCE_INTAKE_GATE_BLOCK,
            resource_id=str(asset.id),
            tenant_id=self.tenant.id,
        ).first()
        self.assertIsNotNone(blocked)
        assert blocked is not None
        self.assertEqual(blocked.actor_user_id, self.user.id)
