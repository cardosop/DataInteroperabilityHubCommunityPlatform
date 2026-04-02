"""
Phase 26-OB: Onboarding lifecycle tests.

Full onboarding lifecycle from asset creation to activation,
covering contract/dataset attachment, activation gates, compliance
blocks, optimistic locking, and error responses.
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
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class OnboardingLifecycleTest(TestCase):
    """Full onboarding lifecycle from creation to activation."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"OB Tenant {uid}",
            slug=f"ob-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"ob-user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)

    # -- helpers -------------------------------------------------------

    def _create_asset(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="Lifecycle Asset",
            created_by=self.user,
        )
        defaults.update(overrides)
        return Asset.objects.create(**defaults)

    def _create_contract(self, asset, **overrides):
        defaults = dict(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"test"}',
            created_by=self.user,
        )
        defaults.update(overrides)
        return Contract.objects.create(**defaults)

    def _create_dataset(self, asset):
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=512,
            storage_path=f"test/{uuid.uuid4().hex}.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
        )

    def _create_compliance_run(self, asset, *, run_status=ComplianceRunStatus.SUCCEEDED, allowed_to_store=True):
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
        return ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            job=job,
            status=run_status,
            allowed_to_store=allowed_to_store,
            completed_at=timezone.now(),
        )

    def _activate(self, asset, version=None):
        v = version if version is not None else asset.version
        return self.client.post(
            f"/api/v1/assets/{asset.id}/activate/",
            {"version": v},
            format="json",
        )

    # -- tests ---------------------------------------------------------

    def test_asset_first_creates_draft(self):
        """POST /api/v1/assets/ creates an asset in DRAFT status."""
        resp = self.client.post(
            "/api/v1/assets/",
            {"key": f"new-{uuid.uuid4().hex[:6]}", "name": "New Asset"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], AssetStatus.DRAFT)

    def test_asset_first_no_contract_no_dataset(self):
        """Freshly created asset has no contracts and no datasets."""
        asset = self._create_asset()
        self.assertEqual(asset.contracts.count(), 0)
        self.assertEqual(asset.datasets.count(), 0)

    def test_attach_dataset_links_correctly(self):
        """Creating a dataset linked to asset records the relationship."""
        asset = self._create_asset()
        ds = self._create_dataset(asset)
        self.assertEqual(asset.datasets.count(), 1)
        self.assertEqual(asset.datasets.first().id, ds.id)

    def test_attach_contract_links_correctly(self):
        """Creating a contract linked to asset records the relationship."""
        asset = self._create_asset()
        ct = self._create_contract(asset)
        self.assertEqual(asset.contracts.count(), 1)
        self.assertEqual(asset.contracts.first().id, ct.id)

    def test_activate_requires_contract(self):
        """Activation without a contract returns 400."""
        asset = self._create_asset()
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_activate_requires_dq_pass_when_dataset_exists(self):
        """Activation with dataset but dq_status=UNKNOWN returns 400."""
        asset = self._create_asset(dq_status=DQStatus.UNKNOWN, compliance_status=ComplianceStatus.PASS)
        self._create_contract(asset)
        self._create_dataset(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_activate_contract_only_no_dq_needed(self):
        """Contract-only asset (no dataset) activates without DQ/compliance checks."""
        asset = self._create_asset()
        self._create_contract(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_activate_full_setup_succeeds(self):
        """Full setup (ACTIVE contract, DQ PASS, compliance PASS) activates to ACTIVE."""
        asset = self._create_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        self._create_dataset(asset)
        self._create_compliance_run(asset, allowed_to_store=True)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_retired_asset_cannot_reactivate(self):
        """Retired asset returns 400 when activation is attempted."""
        asset = self._create_asset(status=AssetStatus.RETIRED)
        self._create_contract(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ASSET_RETIRED", resp.data.get("code", ""))

    def test_concurrent_activation_returns_409(self):
        """Second activation with stale version returns 409."""
        asset = self._create_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        stale_version = asset.version

        # First activation succeeds
        resp1 = self._activate(asset, version=stale_version)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Second activation with same (now stale) version
        resp2 = self._activate(asset, version=stale_version)
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)

    def test_can_activate_returns_detailed_blockers(self):
        """Blocked activation response includes 'details' array with reasons."""
        asset = self._create_asset()
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("details", resp.data)
        self.assertIsInstance(resp.data["details"], list)
        self.assertTrue(len(resp.data["details"]) > 0)

    def test_compliance_allowed_to_store_false_blocks(self):
        """Compliance run with allowed_to_store=False blocks activation with 403."""
        asset = self._create_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        self._create_dataset(asset)
        self._create_compliance_run(asset, allowed_to_store=False)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "compliance_not_allowed_to_store")

    def test_failed_compliance_run_blocks_activation(self):
        """FAILED compliance run blocks activation with 403."""
        asset = self._create_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        self._create_dataset(asset)
        self._create_compliance_run(
            asset,
            run_status=ComplianceRunStatus.FAILED,
            allowed_to_store=True,
        )
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_version_mismatch_returns_409(self):
        """Activation with wrong version returns 409 CONFLICT."""
        asset = self._create_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        resp = self._activate(asset, version=asset.version + 999)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "ASSET_CONCURRENT_MODIFICATION")

    def test_already_active_returns_400(self):
        """Activating an already-ACTIVE asset returns 400."""
        asset = self._create_asset(
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._create_contract(asset)
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ALREADY_ACTIVE")
