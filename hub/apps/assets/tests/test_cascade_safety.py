"""
Phase 26-OB: Cascade / SET_NULL safety tests.

Ensures that deleting parent entities preserves audit records
(DQ runs, compliance runs) via SET_NULL, and that CASCADE
behaves correctly where expected.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
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
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class CascadeSafetyTest(TestCase):
    """Test FK on_delete behaviour preserves audit records."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cascade Tenant {uid}",
            slug=f"cascade-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"cascade-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name=f"Asset {uid}",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    # -- helpers ----------------------------------------------------------

    def _make_file(self):
        uid = uuid.uuid4().hex[:6]
        return File.objects.create(
            tenant=self.tenant,
            name=f"file-{uid}.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"tenants/{self.tenant.id}/files/{uid}.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

    def _make_dataset(self, file_obj=None):
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file_obj,
            format="CSV",
            row_count=10,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

    def _make_dq_job(self, dataset):
        return create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DATASET",
            resource_id=str(dataset.id),
        )

    def _make_compliance_job(self, dataset):
        return create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="DATASET",
            resource_id=str(dataset.id),
        )

    # -- SET_NULL preserves audit records ---------------------------------

    def test_delete_dataset_preserves_dq_runs(self):
        """Deleting a dataset leaves its DQ runs with dataset=None."""
        ds = self._make_dataset()
        job = self._make_dq_job(ds)
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=ds,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
        )
        ds.delete()
        dq_run.refresh_from_db()
        self.assertIsNone(dq_run.dataset)
        self.assertEqual(dq_run.overall_status, "PASS")

    def test_delete_dataset_preserves_compliance_runs(self):
        """Deleting a dataset leaves its compliance runs with dataset=None."""
        ds = self._make_dataset()
        job = self._make_compliance_job(ds)
        comp_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=ds,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level="LOW",
            allowed_to_store=True,
        )
        ds.delete()
        comp_run.refresh_from_db()
        self.assertIsNone(comp_run.dataset)
        self.assertEqual(comp_run.overall_status, "PASS")

    def test_delete_file_preserves_dataset(self):
        """Deleting a file leaves the dataset with file=None (SET_NULL)."""
        f = self._make_file()
        ds = self._make_dataset(file_obj=f)
        f.delete()
        ds.refresh_from_db()
        self.assertIsNone(ds.file)

    # -- CASCADE where expected -------------------------------------------

    def test_delete_asset_cascades_contracts(self):
        """Deleting an asset cascades to its contracts."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"c"}',
            created_by=self.user,
        )
        contract_id = contract.id
        self.asset.delete()
        self.assertFalse(Contract.objects.filter(id=contract_id).exists())

    def test_delete_asset_cascades_datasets(self):
        """Deleting an asset cascades to its datasets."""
        ds = self._make_dataset()
        ds_id = ds.id
        self.asset.delete()
        self.assertFalse(Dataset.objects.filter(id=ds_id).exists())

    # -- RETIRED does not delete ------------------------------------------

    def test_retire_asset_preserves_all(self):
        """Setting asset to RETIRED does not delete contracts or datasets."""
        Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"c"}',
            created_by=self.user,
        )
        self._make_dataset()
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, AssetStatus.RETIRED)
        self.assertTrue(self.asset.contracts.exists())
        self.assertTrue(self.asset.datasets.exists())

    # -- Data integrity after delete --------------------------------------

    def test_dq_run_data_preserved_after_dataset_delete(self):
        """DQ run checks_json and quality_score survive dataset deletion."""
        ds = self._make_dataset()
        job = self._make_dq_job(ds)
        checks = [{"check": "not_null", "column": "id", "passed": True}]
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=ds,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=98.5,
            checks_json=checks,
        )
        ds.delete()
        dq_run.refresh_from_db()
        self.assertIsNone(dq_run.dataset)
        self.assertEqual(dq_run.quality_score, 98.5)
        self.assertEqual(dq_run.checks_json, checks)

    def test_compliance_run_data_preserved_after_dataset_delete(self):
        """Compliance run overall_status, risk_level, allowed_to_store survive dataset deletion."""
        ds = self._make_dataset()
        job = self._make_compliance_job(ds)
        comp_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=ds,
            job=job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="WARN",
            risk_level="MEDIUM",
            allowed_to_store=True,
        )
        ds.delete()
        comp_run.refresh_from_db()
        self.assertIsNone(comp_run.dataset)
        self.assertEqual(comp_run.overall_status, "WARN")
        self.assertEqual(comp_run.risk_level, "MEDIUM")
        self.assertTrue(comp_run.allowed_to_store)
