"""
Tests for file resolution in execute_compliance_run().

Validates the file-lookup priority: direct file > dataset.file >
asset's latest dataset's file, plus error handling for missing files
and S3 failures. All tests use real infrastructure (no mocks).
"""
import time
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.views import execute_compliance_run
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File as FileModel
from hub.apps.files.storage import S3StorageClient
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
        file_id = uuid.uuid4()
        self.storage_path = f"{self.tenant.id}/{file_id}/test-data.csv"
        self.file_obj = FileModel.objects.create(
            tenant=self.tenant,
            name="test-data.csv",
            content_type="text/csv",
            storage_path=self.storage_path,
            size=1024,
            content_sha256="a" * 64,
        )
        # Upload real test file content to MinIO so storage-dependent
        # tests operate against real infrastructure.
        self._upload_test_file()

    def _upload_test_file(self):
        """Upload test CSV content to real MinIO storage."""
        max_attempts = 6
        delay_seconds = 3
        for attempt in range(max_attempts):
            try:
                storage_client = S3StorageClient()
                storage_client._ensure_bucket_exists()
                storage_client.upload_file(
                    file_path=self.storage_path,
                    file_content=b"col1,col2\nval1,val2",
                    content_type="text/csv",
                )
                return
            except (ConnectionError, OSError):
                if attempt < max_attempts - 1:
                    time.sleep(delay_seconds)
                    continue

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

    def _poll_to_terminal(self, run, max_attempts=15):
        """Poll an async (QUEUED) compliance run to a terminal state.

        Calls ``poll_compliance_job`` inline in a short loop so the test can
        assert a specific expected outcome rather than accept 3 different
        statuses (SUCCEEDED / FAILED / QUEUED).

        A 1-second sleep between attempts gives the compliance-scan RQ worker
        time to process the job before the next poll.
        """
        import time as _time
        from hub.apps.compliance.tasks import poll_compliance_job

        for _ in range(max_attempts):
            if run.status in (
                ComplianceRunStatus.SUCCEEDED,
                ComplianceRunStatus.FAILED,
            ):
                return
            poll_compliance_job(run.id)
            run.refresh_from_db()
            if run.status not in (
                ComplianceRunStatus.SUCCEEDED,
                ComplianceRunStatus.FAILED,
            ):
                _time.sleep(1)

    # ----------------------------------------------------------------
    # 1. File resolved from direct file FK
    # ----------------------------------------------------------------

    def test_file_resolved_from_direct_file(self):
        """ComplianceRun with file set uses that file directly (real storage)."""
        run = self._create_run(file=self.file_obj)
        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        # Drive async (QUEUED) run to a terminal state so we can assert
        # the expected outcome rather than accept 3 different statuses.
        self._poll_to_terminal(run)
        run.refresh_from_db()
        self.assertEqual(
            run.status, ComplianceRunStatus.SUCCEEDED,
            f"Expected SUCCEEDED; regulation_mapping_json error: "
            f"{(run.regulation_mapping_json or {}).get('error', 'none')}",
        )
        # Verify the run's file was resolved and the service was called.
        mapping = run.regulation_mapping_json or {}
        self.assertIn("metering", mapping)

    # ----------------------------------------------------------------
    # 2. File resolved from dataset
    # ----------------------------------------------------------------

    def test_file_resolved_from_dataset(self):
        """ComplianceRun with dataset that has a file uses dataset's file."""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            format="csv",
            version=1,
            created_by=self.user,
        )
        run = self._create_run(dataset=dataset, file=None)
        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        self._poll_to_terminal(run)
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)

    # ----------------------------------------------------------------
    # 3. File resolved from asset's latest dataset
    # ----------------------------------------------------------------

    def test_file_resolved_from_asset_latest_dataset(self):
        """ComplianceRun with asset only resolves to asset's latest dataset's file."""
        older_file = FileModel.objects.create(
            tenant=self.tenant,
            name="old-data.csv",
            content_type="text/csv",
            storage_path=self.storage_path,
            size=512,
            content_sha256="b" * 64,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=older_file,
            format="csv",
            version=1,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file_obj,
            format="csv",
            version=2,
            created_by=self.user,
        )

        run = self._create_run(file=None, dataset=None)
        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        self._poll_to_terminal(run)
        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.SUCCEEDED)

    # ----------------------------------------------------------------
    # 4. No file raises error and marks FAILED
    # ----------------------------------------------------------------

    def test_no_file_raises_error(self):
        """ComplianceRun with no file/dataset/asset-with-dataset marks run FAILED."""
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
    # 5. Real S3 error marks FAILED with fail-closed
    # ----------------------------------------------------------------

    def test_s3_error_marks_failed(self):
        """Non-existent storage_path triggers real NoSuchKey error, marks run FAILED."""
        run = self._create_run(file=self.file_obj)
        # Point to a storage path that genuinely does not exist in MinIO.
        # The real S3StorageClient will raise NoSuchKey, which
        # execute_compliance_run catches and persists as FAILED.
        nonexistent_path = f"{self.tenant.id}/nonexistent/does/not/exist.csv"
        self.file_obj.storage_path = nonexistent_path
        self.file_obj.save(update_fields=["storage_path"])

        execute_compliance_run(str(run.id))

        run.refresh_from_db()
        self.assertEqual(run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(run.allowed_to_store)
        self.assertTrue(run.regulation_mapping_json.get("fail_closed"))
