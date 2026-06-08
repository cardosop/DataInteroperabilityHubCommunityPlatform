"""
Integration tests for DQ/compliance execution (T.10).

Tests DQ and compliance job execution, result storage, and asset status updates.

Note: These tests require DQ and Compliance services to be running.
Start services with: make docker-up-services

All tests use real services with graceful handling when services unavailable.
"""

import os
import time
import urllib.request

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _check_health_stdlib(health_url: str, timeout_seconds: int = 20, interval: float = 2.0) -> bool:
    """
    Check service health using stdlib only (urllib).
    Matches batch script behavior so integration tests see the same readiness as the script.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)  # INTENTIONAL: test-specific timing requirement
    return False


@pytest.mark.integration
class DQComplianceExecutionTest(DQAPITestBase):
    """Integration tests for DQ/compliance execution (T.10)"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Check if services are available (stdlib-only health check; matches batch script)
        dq_url = os.getenv("DQ_SERVICE_URL", "http://localhost:8083")
        compliance_url = os.getenv("COMPLIANCE_SERVICE_URL", "http://localhost:8082")

        # Replace only non-test Docker hostnames with localhost (e.g. dq-service:8083).
        # Leave dq-service-test / compliance-service-test unchanged when running in Docker.
        if "dq-service-test" not in dq_url and "dq-service" in dq_url:
            dq_url = dq_url.replace("dq-service", "localhost")
        if "compliance-service-test" not in compliance_url and "compliance-service" in compliance_url:
            compliance_url = compliance_url.replace("compliance-service", "localhost")

        dq_health = (dq_url.rstrip("/") + "/health") if dq_url else ""
        compliance_health = (compliance_url.rstrip("/") + "/health") if compliance_url else ""
        self.dq_service_available = bool(
            dq_health and _check_health_stdlib(dq_health, timeout_seconds=20)
        )
        self.compliance_service_available = bool(
            compliance_health and _check_health_stdlib(compliance_health, timeout_seconds=20)
        )

        # Check if storage is available and upload test file content (same pattern as
        # test_dq_execution; uses S3StorageClient so config matches app—no mocks)
        self.storage_available = False
        self._storage_check_error = None
        for attempt in range(4):
            try:
                storage_client = S3StorageClient()
                storage_client._ensure_bucket_exists()
                test_content = b"id,name\n1,Test\n2,Sample"
                storage_path = storage_client.save_file(
                    tenant_id=str(self.tenant.id),
                    file_id=str(self.file.id),
                    file_content=ContentFile(test_content),
                )
                self.file.storage_path = storage_path
                self.file.save(update_fields=["storage_path"])
                self.storage_available = True
                break
            except Exception as e:
                self._storage_check_error = e
                if attempt < 3:
                    time.sleep(3)  # INTENTIONAL: test-specific timing requirement
                else:
                    import sys

                    sys.stderr.write(
                        "[DQ integration] Storage check failed after 4 attempts: %s\n"
                        % (e,)
                    )
                    sys.stderr.flush()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    def _integration_skip_reason(self, need_dq=False, need_compliance=False, need_storage=False):
        """Return skip reason including dependency state for diagnostics (no mocks)."""
        state = "dq=%s compliance=%s storage=%s" % (
            self.dq_service_available,
            self.compliance_service_available,
            self.storage_available,
        )
        if need_dq and not self.dq_service_available:
            return "DQ service not available (%s)" % state
        if need_compliance and not self.compliance_service_available:
            return "Compliance service not available (%s)" % state
        if need_storage and not self.storage_available:
            err = getattr(self, "_storage_check_error", None)
            detail = " (%s)" % err if err else ""
            return "Storage not available (%s)%s" % (state, detail)
        return "Integration deps unavailable (%s)" % state

    def _skip_if_unavailable(self, reason: str) -> None:
        """Skip test and ensure reason is visible in batch logs (no -rs required)."""
        import sys
        sys.stderr.write("[DQ integration] SKIP: %s\n" % reason)
        sys.stderr.flush()
        self.skipTest(reason)

    def test_dq_execution_flow(self):
        """Test DQ execution flow with real services"""
        if not self.dq_service_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_dq=True))
        if not self.storage_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_storage=True))

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        # Create DQ run via API
        response = self.client.post(
            "/api/v1/dq/runs/",
            {
                "file_id": str(self.file.id),
                "dataset_id": str(dataset.id),
                "asset_id": str(self.asset.id),
                "profile_key": "intake_basic_gx",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify DQ run was created
        dq_run = DQRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(dq_run)
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)  # Initially PENDING

        # Execute the DQ run synchronously (simulating job execution)
        from hub.apps.dq.views import execute_dq_run

        try:
            execute_dq_run(str(dq_run.id))
        except Exception as e:
            # If execution fails due to service issues, verify fail-closed behavior
            dq_run.refresh_from_db()
            if dq_run.status == DQRunStatus.FAILED:
                self.assertIn("error", dq_run.details_json)
                return
            raise

        # Refresh and verify DQ run was updated
        dq_run.refresh_from_db()
        # Status could be SUCCEEDED or FAILED depending on service response
        self.assertIn(dq_run.status, [DQRunStatus.SUCCEEDED, DQRunStatus.FAILED])

        if dq_run.status == DQRunStatus.SUCCEEDED:
            self.assertIsNotNone(dq_run.overall_status)
            self.assertIsNotNone(dq_run.quality_score)

        # Verify job was created
        job = Job.objects.filter(type=JobType.DQ_RUN, resource_id=str(dq_run.id)).first()
        self.assertIsNotNone(job)

    def test_compliance_execution_flow(self):
        """Test compliance execution flow with real services"""
        if not self.compliance_service_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_compliance=True))
        if not self.storage_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_storage=True))

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        # Create compliance run via API
        response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(self.file.id),
                "dataset_id": str(dataset.id),
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify compliance run was created
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(compliance_run)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)  # Initially PENDING

        # Execute the compliance run synchronously (simulating job execution)
        from hub.apps.compliance.views import execute_compliance_run

        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception as e:
            # If execution fails due to service issues, verify fail-closed behavior
            compliance_run.refresh_from_db()
            if compliance_run.status == ComplianceRunStatus.FAILED:
                self.assertFalse(compliance_run.allowed_to_store)
                return
            raise

        # Refresh and verify compliance run was updated
        compliance_run.refresh_from_db()
        # Status could be SUCCEEDED, FAILED, or QUEUED (async path where
        # the compliance service returned 202 and a polling task was enqueued)
        self.assertIn(
            compliance_run.status,
            [ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED, ComplianceRunStatus.QUEUED],
        )

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIsNotNone(compliance_run.overall_status)
            self.assertIsNotNone(compliance_run.allowed_to_store)
        elif compliance_run.status == ComplianceRunStatus.QUEUED:
            # Async path: overall_status and allowed_to_store are set after
            # the polling task retrieves the result from the compliance service
            self.assertIsNotNone(compliance_run.metadata_json)
            self.assertIn("job_id", compliance_run.metadata_json)

        # Verify job was created
        job = Job.objects.filter(
            type=JobType.COMPLIANCE_RUN, resource_id=str(compliance_run.id)
        ).first()
        self.assertIsNotNone(job)

    def test_dq_compliance_fail_closed_behavior(self):
        """Test fail-closed behavior when DQ or compliance fails"""
        if not self.compliance_service_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_compliance=True))
        if not self.storage_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_storage=True))

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        # Create compliance run (may fail depending on service response)
        compliance_response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(self.file.id),
                "dataset_id": str(dataset.id),
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )
        self.assertEqual(compliance_response.status_code, status.HTTP_201_CREATED)

        # Compliance run should be created (status will be PENDING until job completes)
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()
        self.assertIsNotNone(compliance_run)

        # Execute the compliance run synchronously (simulating job execution)
        from hub.apps.compliance.views import execute_compliance_run

        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception:
            # If execution fails, verify fail-closed behavior
            compliance_run.refresh_from_db()
            if compliance_run.status == ComplianceRunStatus.FAILED:
                self.assertFalse(compliance_run.allowed_to_store)
                return

        # Refresh and verify fail-closed behavior
        compliance_run.refresh_from_db()
        # If compliance fails, allowed_to_store should be False
        if compliance_run.overall_status == "FAIL":
            self.assertFalse(compliance_run.allowed_to_store)

    def test_asset_status_update_on_dq_compliance(self):
        """Test asset status updates based on DQ and compliance results"""
        if not self.dq_service_available or not self.compliance_service_available:
            self._skip_if_unavailable(
                self._integration_skip_reason(need_dq=True, need_compliance=True)
            )
        if not self.storage_available:
            self._skip_if_unavailable(self._integration_skip_reason(need_storage=True))

        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="csv",
            created_by=self.user,
        )

        # Create compliance and DQ runs
        compliance_response = self.client.post(
            "/api/v1/compliance/runs/",
            {
                "file_id": str(self.file.id),
                "dataset_id": str(dataset.id),
                "asset_id": str(self.asset.id),
                "scan_mode": "internal",
            },
            format="json",
        )
        self.assertEqual(compliance_response.status_code, status.HTTP_201_CREATED)

        dq_response = self.client.post(
            "/api/v1/dq/runs/",
            {
                "file_id": str(self.file.id),
                "dataset_id": str(dataset.id),
                "asset_id": str(self.asset.id),
            },
            format="json",
        )
        self.assertEqual(dq_response.status_code, status.HTTP_201_CREATED)

        # Get the runs
        dq_run = DQRun.objects.filter(dataset=dataset).first()
        compliance_run = ComplianceRun.objects.filter(dataset=dataset).first()

        self.assertIsNotNone(dq_run)
        self.assertIsNotNone(compliance_run)

        # Execute both runs synchronously (simulating job execution)
        from hub.apps.compliance.views import execute_compliance_run
        from hub.apps.dq.views import execute_dq_run

        try:
            execute_dq_run(str(dq_run.id))
        except Exception as exc:
            # If execution fails, verify it's a legitimate failure, not a
            # spurious exception (e.g. AttributeError from a refactoring bug).
            dq_run.refresh_from_db()
            if dq_run.status == DQRunStatus.FAILED:
                pass  # Expected — run correctly recorded its own failure
            else:
                raise AssertionError(
                    f"execute_dq_run raised {type(exc).__name__}: {exc} "
                    f"but dq_run.status={dq_run.status}, not FAILED"
                ) from exc

        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception as exc:
            compliance_run.refresh_from_db()
            if compliance_run.status == ComplianceRunStatus.FAILED:
                pass  # Expected — run correctly recorded its own failure
            else:
                raise AssertionError(
                    f"execute_compliance_run raised {type(exc).__name__}: {exc} "
                    f"but compliance_run.status={compliance_run.status}, not FAILED"
                ) from exc

        # Refresh and verify runs were updated
        dq_run.refresh_from_db()
        compliance_run.refresh_from_db()

        # Verify runs have terminal or async-queued status
        self.assertIn(
            dq_run.status,
            [DQRunStatus.SUCCEEDED, DQRunStatus.FAILED],
        )
        self.assertIn(
            compliance_run.status,
            [ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED, ComplianceRunStatus.QUEUED],
        )

        # overall_status is only set once execution completes (not when QUEUED)
        if dq_run.status == DQRunStatus.SUCCEEDED:
            self.assertIsNotNone(dq_run.overall_status)
        if compliance_run.status in (ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED):
            self.assertIsNotNone(compliance_run.overall_status)
        elif compliance_run.status == ComplianceRunStatus.QUEUED:
            # Async path: result pending polling task completion
            self.assertIsNotNone(compliance_run.metadata_json)

        # Verify asset status was updated if runs succeeded
        self.asset.refresh_from_db()
        if (
            dq_run.status == DQRunStatus.SUCCEEDED
            and compliance_run.status == ComplianceRunStatus.SUCCEEDED
        ):
            # Asset DQ status should be updated
            self.assertIsNotNone(self.asset.dq_status)
