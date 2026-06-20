"""
Phase 26-OB: Activation endpoint blocker tests.

Tests POST /api/v1/assets/{id}/activate/ returns correct blockers
for various combinations of contract, DQ, and compliance state.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class ActivationBlockersAPITest(TestCase):
    """Test the activation endpoint returns correct blockers."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Block Tenant {uid}",
            slug=f"block-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"block-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    # -- helpers ----------------------------------------------------------

    def _make_asset(self, dq=DQStatus.UNKNOWN, compliance=ComplianceStatus.UNKNOWN):
        uid = uuid.uuid4().hex[:6]
        return Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name=f"Asset {uid}",
            status=AssetStatus.DRAFT,
            dq_status=dq,
            compliance_status=compliance,
            created_by=self.user,
        )

    def _make_contract(
        self,
        asset,
        *,
        con_status=ContractStatus.ACTIVE,
        val_status=ValidationStatus.VALID,
        norm_status=NormalizationStatus.NORMALIZED_OK,
    ):
        return Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=con_status,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"t","name":"T","schema":{"fields":[{"name":"id","type":"string"}]}}',
            validation_status=val_status,
            normalization_status=norm_status,
            created_by=self.user,
        )

    def _make_dataset(self, asset):
        f = File.objects.create(
            tenant=self.tenant,
            name=f"f-{uuid.uuid4().hex[:6]}.csv",
            content_type="text/csv",
            size=256,
            storage_path=f"tenants/{self.tenant.id}/files/{uuid.uuid4().hex}.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=f,
            format="CSV",
            row_count=10,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

    def _make_compliance_run(
        self,
        asset,
        dataset,
        *,
        run_status=ComplianceRunStatus.SUCCEEDED,
        overall="PASS",
        risk="LOW",
        allowed=True,
    ):
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="DATASET",
            resource_id=str(dataset.id),
        )
        return ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            dataset=dataset,
            job=job,
            status=run_status,
            overall_status=overall,
            risk_level=risk,
            allowed_to_store=allowed,
            completed_at=timezone.now(),
        )

    def _activate(self, asset):
        return self.client.post(
            f"/api/v1/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json",
        )

    # -- contract blockers ------------------------------------------------

    def test_no_contract_returns_blocker(self):
        """No contract -> 400 with blocker about ACTIVE contract."""
        asset = self._make_asset()
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ACTIVE contract", str(resp.data))

    def test_draft_contract_returns_blocker(self):
        """DRAFT contract -> 400 blocker about missing ACTIVE contract."""
        asset = self._make_asset()
        self._make_contract(asset, con_status=ContractStatus.DRAFT)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ACTIVE contract", str(resp.data))

    def test_invalid_contract_returns_blocker(self):
        """Contract validation=INVALID -> 400 blocker about validation."""
        asset = self._make_asset()
        self._make_contract(asset, val_status=ValidationStatus.INVALID)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("validation_status", str(resp.data))

    # -- DQ blockers ------------------------------------------------------

    def test_dq_unknown_returns_blocker(self):
        """Dataset exists + dq_status=UNKNOWN -> 400 blocker."""
        asset = self._make_asset(dq=DQStatus.UNKNOWN, compliance=ComplianceStatus.PASS)
        self._make_contract(asset)
        self._make_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("dq_status", str(resp.data))

    def test_dq_fail_returns_blocker(self):
        """Dataset exists + dq_status=FAIL -> 400 blocker."""
        asset = self._make_asset(dq=DQStatus.FAIL, compliance=ComplianceStatus.PASS)
        self._make_contract(asset)
        self._make_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("dq_status", str(resp.data))

    # -- compliance blockers ----------------------------------------------

    def test_compliance_unknown_returns_blocker(self):
        """Dataset exists + compliance_status=UNKNOWN -> 400 blocker."""
        asset = self._make_asset(dq=DQStatus.PASS, compliance=ComplianceStatus.UNKNOWN)
        self._make_contract(asset)
        self._make_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("compliance_status", str(resp.data))

    def test_compliance_fail_returns_blocker(self):
        """Dataset exists + compliance_status=FAIL -> 400 blocker."""
        asset = self._make_asset(dq=DQStatus.PASS, compliance=ComplianceStatus.FAIL)
        self._make_contract(asset)
        self._make_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("compliance_status", str(resp.data))

    # -- success cases ----------------------------------------------------

    def test_no_dataset_no_dq_blocker(self):
        """Contract-only asset (no dataset) activates without DQ/compliance."""
        asset = self._make_asset()
        self._make_contract(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_all_pass_activates(self):
        """Valid contract + DQ PASS + compliance PASS -> 200, ACTIVE."""
        asset = self._make_asset(dq=DQStatus.PASS, compliance=ComplianceStatus.PASS)
        self._make_contract(asset)
        ds = self._make_dataset(asset)
        self._make_compliance_run(asset, ds)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_warn_statuses_activate(self):
        """DQ WARN + compliance WARN -> activation succeeds."""
        asset = self._make_asset(dq=DQStatus.WARN, compliance=ComplianceStatus.WARN)
        self._make_contract(asset)
        ds = self._make_dataset(asset)
        self._make_compliance_run(asset, ds, overall="WARN", risk="MEDIUM")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    # -- multiple blockers ------------------------------------------------

    def test_contract_blocker_returned_when_no_contract(self):
        """Without a contract, the contract blocker is returned first.

        DQ and compliance blockers only appear when a dataset exists AND
        the contract check already passed.  With no contract the blocker
        list may only contain the contract message — verify at least one
        blocker is returned."""
        asset = self._make_asset(dq=DQStatus.FAIL, compliance=ComplianceStatus.FAIL)
        self._make_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        details = resp.data.get("details", [])
        details_str = str(details)
        self.assertIn("ACTIVE contract", details_str)
        self.assertGreaterEqual(len(details), 1)

    # -- compliance run blocks activation ---------------------------------

    def test_failed_compliance_run_blocks(self):
        """Compliance run with status=FAILED -> 403 compliance_not_allowed_to_store."""
        asset = self._make_asset(dq=DQStatus.PASS, compliance=ComplianceStatus.PASS)
        self._make_contract(asset)
        ds = self._make_dataset(asset)
        self._make_compliance_run(
            asset,
            ds,
            run_status=ComplianceRunStatus.FAILED,
            overall="FAIL",
            risk="HIGH",
            allowed=False,
        )
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "compliance_not_allowed_to_store")
