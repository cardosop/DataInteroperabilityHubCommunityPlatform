"""
Tests for file resolution in execute_compliance_run().

Validates the file-lookup priority: direct file > dataset.file >
asset's latest dataset's file, plus error handling for missing files
and S3 failures.
"""
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.views import execute_compliance_run
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File as FileModel
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class FileResolutionTest(TestCase):
    """Tests for file resolution in execute_compliance_run()."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.file_obj = FileModel.objects.create(
            tenant=self.tenant,
            name="test-data.csv",
            content_type="text/csv",
            storage_path=f"tenants/{self.tenant.id}/files/test-data.csv",
            size=1024,
            content_sha256="a" * 64,
        )

    def _create_job(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={
                "scan_mode": "internal",
                "applicable_regulations": ["GDPR"],
            },
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        defaults.update(overrides)
        return create_job(**defaults)

    def _create_run(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            asset=self.asset,
            job=self._create_job(),
            status=ComplianceRunStatus.PENDING,
        )
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    # ----------------------------------------------------------------
    # 1. File resolved from direct file FK
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.views.ComplianceService._call_compliance_service")
    @patch("hub.apps.files.storage.S3StorageClient")
    def test_file_resolved_from_direct_file(self, MockS3, mock_call):
        """ComplianceRun with file set uses that file directly."""
        mock_s3_instance = MockS3.return_value
        mock_s3_instance.get_file_content.return_value = b"col1,col2\nval1,val2"

        run = self._create_run(file=self.file_obj)
        execute_compliance_run(str(run.id))

        mock_s3_instance.get_file_content.assert_called_once_with(
            self.file_obj.storage_path
        )
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args.kwargs
        self.assertEqual(call_kwargs["file_content"], b"col1,col2\nval1,val2")
        self.assertEqual(call_kwargs["file_format"], "csv")

    # ----------------------------------------------------------------
    # 2. File resolved from dataset
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.views.ComplianceService._call_compliance_service")
    @patch("hub.apps.files.storage.S3StorageClient")
    def test_file_resolved_from_dataset(self, MockS3, mock_call):
        """ComplianceRun with dataset that has a file uses dataset's file."""
        mock_s3_instance = MockS3.return_value
        mock_s3_instance.get_file_content.return_value = b"dataset content"

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            format="csv",
            version=1,
        )
        run = self._create_run(dataset=dataset, file=None)
        execute_compliance_run(str(run.id))

        mock_s3_instance.get_file_content.assert_called_once_with(
            self.file_obj.storage_path
        )
        mock_call.assert_called_once()

    # ----------------------------------------------------------------
    # 3. File resolved from asset's latest dataset
    # ----------------------------------------------------------------

    @patch("hub.apps.compliance.views.ComplianceService._call_compliance_service")
    @patch("hub.apps.files.storage.S3StorageClient")
    def test_file_resolved_from_asset_latest_dataset(self, MockS3, mock_call):
        """ComplianceRun with asset only resolves to asset's latest dataset's file."""
        mock_s3_instance = MockS3.return_value
        mock_s3_instance.get_file_content.return_value = b"latest ds content"

        # Create two datasets; the latest (higher version) should be picked
        older_file = FileModel.objects.create(
            tenant=self.tenant,
            name="old-data.csv",
            content_type="text/csv",
            storage_path=f"tenants/{self.tenant.id}/files/old-data.csv",
            size=512,
            content_sha256="b" * 64,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=older_file,
            format="csv",
            version=1,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            format="csv",
            version=2,
        )

        run = self._create_run(file=None, dataset=None)
        execute_compliance_run(str(run.id))

        # Should use the latest dataset's file (version=2 -> self.file_obj)
        mock_s3_instance.get_file_content.assert_called_once_with(
            self.file_obj.storage_path
        )

    # ----------------------------------------------------------------
    # 4. No file raises error and marks FAILED
    # ----------------------------------------------------------------

    @patch("hub.apps.files.storage.S3StorageClient")
    def test_no_file_raises_error(self, MockS3):
        """ComplianceRun with no file/dataset/asset-with-dataset marks run FAILED."""
        # Asset with no datasets → no file resolvable
        empty_uid = uuid.uuid4().hex[:8]
        empty_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"empty-asset-{empty_uid}",
            name="Empty Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        run = self._create_run(asset=empty_asset, file=None, dataset=None)
        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertIn("error", run.regulation_mapping_json)

    # ----------------------------------------------------------------
    # 5. S3 error marks FAILED with fail-closed
    # ----------------------------------------------------------------

    @patch("hub.apps.files.storage.S3StorageClient")
    def test_s3_error_marks_failed(self, MockS3):
        """S3StorageClient.get_file_content raising marks run FAILED, fail-closed."""
        mock_s3_instance = MockS3.return_value
        mock_s3_instance.get_file_content.side_effect = Exception(
            "S3 connection refused"
        )

        run = self._create_run(file=self.file_obj)
        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertTrue(run.regulation_mapping_json.get("fail_closed"))
