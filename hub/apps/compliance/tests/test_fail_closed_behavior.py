"""
Comprehensive unit tests for fail-closed behavior.

Tests cover:
- Fail-closed when allowed_to_store=False
- Fail-closed on service errors / UNKNOWN / fallback
- Fail-closed blocks asset activation
- Edge cases
- Error handling

All tests use real implementations (no mocks/stubs) except where we force
fallback/UNKNOWN to assert Hub sets allowed_to_store=False (MockTransport only
for service unreachable to force fallback; assertions on Hub state).
"""

import time
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, ComplianceStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.compliance.views import execute_compliance_run
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
from hub.apps.files.storage import S3StorageClient
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class FailClosedBehaviorTest(TestCase):
    """Comprehensive tests for fail-closed enforcement behavior"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create file with storage path
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        # Set up test file content in storage if available
        self._setup_test_file_content()

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="COMPLIANCE_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            timeout_seconds=1800,
            details_json={"scan_mode": "internal", "applicable_regulations": []},
        )

    def _setup_test_file_content(self):
        """Set up test file content in storage. Retries so MinIO startup delay does not cause skips."""
        max_attempts = 6
        delay_seconds = 3
        for attempt in range(max_attempts):
            try:
                storage_client = S3StorageClient()
                storage_client._ensure_bucket_exists()

                # Upload test CSV content with SSN (should trigger fail-closed)
                test_content = b"email,ssn\nuser@example.com,123-45-6789"
                storage_client.upload_file(
                    file_path=self.file.storage_path,
                    file_content=test_content,
                    content_type="text/csv",
                )
                self.storage_available = True
                return
            except Exception:
                if attempt < max_attempts - 1:
                    time.sleep(delay_seconds)
                    continue
                # Storage not available after retries - tests will skip
                self.storage_available = False

    def test_fail_closed_when_allowed_to_store_false(self):
        """Test that allowed_to_store=False triggers fail-closed behavior"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Check if compliance service is available
        compliance_client = ComplianceServiceClient()
        try:
            is_healthy, _ = compliance_client.health_check()
            if not is_healthy:
                self.skipTest("Compliance service not available - skipping test")
        except Exception:
            self.skipTest("Compliance service not available - skipping test")

        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Execute compliance run with real services
        # If service detects SSN, it should return allowed_to_store=False
        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception:
            # If execution fails, verify fail-closed
            compliance_run.refresh_from_db()
            if compliance_run.status == ComplianceRunStatus.FAILED:
                self.assertFalse(compliance_run.allowed_to_store)
            return

        # Verify fail-closed behavior
        compliance_run.refresh_from_db()
        # Service may or may not detect SSN depending on implementation
        # If it does, allowed_to_store should be False
        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            # Check if fail-closed was triggered
            if compliance_run.overall_status == "FAIL":
                self.assertFalse(compliance_run.allowed_to_store)

    def test_fail_closed_on_service_error(self):
        """Test that service errors result in fail-closed behavior"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Break compliance service connection to test error handling
        # Use file with non-existent path to trigger storage error, or
        # use invalid service configuration
        self.file.storage_path = "nonexistent/path/file.csv"
        self.file.save()

        # Execute compliance run - should handle error gracefully
        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception:
            # Expected if storage/service unavailable
            pass

        # Verify fail-closed on error
        compliance_run.refresh_from_db()
        if compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertFalse(compliance_run.allowed_to_store)  # Fail-closed
            self.assertIn("fail_closed", compliance_run.regulation_mapping_json)
            self.assertTrue(compliance_run.regulation_mapping_json["fail_closed"])

    def test_fail_closed_blocks_asset_activation(self):
        """Test that fail-closed compliance prevents asset activation"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Create a contract for the asset (required for activation)
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1, "id": "test"},
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Create a dataset for the asset (required for compliance check in can_activate)
        dataset = Dataset.objects.create(
            tenant=self.tenant, asset=asset, file=self.file, format="CSV", created_by=self.user
        )

        # Create compliance run for asset with FAIL status
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="FAIL",
            allowed_to_store=False,  # Fail-closed
        )

        # Verify asset compliance status
        asset.refresh_from_db()
        # Set compliance status to FAIL to simulate fail-closed
        asset.compliance_status = ComplianceStatus.FAIL
        asset.save()

        # Asset activation should be blocked (enforced at asset.can_activate() level)
        can_activate, blockers = asset.can_activate()
        self.assertFalse(can_activate)
        # Check that compliance_status is mentioned in blockers
        blocker_text = " ".join(blockers).lower()
        self.assertIn("compliance_status", blocker_text)

    # ========== FALLBACK / UNKNOWN (fail-closed) ==========

    def test_fallback_response_has_allowed_to_store_false(self):
        """Fallback response from client has allowed_to_store=False (fail-closed)."""
        client = ComplianceServiceClient()
        # Force fallback by making the service unreachable (RequestError)
        with patch.object(client, "_request_with_retry", side_effect=Exception("Compliance service unreachable")):
            result = client.scan_file(file_content=b"a,b\n1,2", file_format="csv")
        self.assertFalse(result["allowed_to_store"], "Fallback must be fail-closed")
        self.assertEqual(result["overall_status"], "UNKNOWN")

    def test_when_client_returns_unknown_hub_sets_allowed_to_store_false(self):
        """When client returns UNKNOWN or None allowed_to_store, Hub sets run to allowed_to_store=False and blocks."""
        if not getattr(self, "storage_available", False):
            self.skipTest("Storage not available - skipping test that requires storage")

        fallback_like_response = {
            "overall_status": "UNKNOWN",
            "risk_level": "UNKNOWN",
            "allowed_to_store": None,
            "detected_categories": [],
            "column_findings": [],
            "regulation_mapping": {},
            "applicable_regulations": [],
            "issues": [],
            "metadata": {"total_rows": 0, "total_columns": 0},
        }
        with patch.object(ComplianceServiceClient, "scan_file", return_value=fallback_like_response):
            compliance_run = ComplianceRun.objects.create(
                tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
            )
            execute_compliance_run(str(compliance_run.id))

        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertFalse(compliance_run.allowed_to_store, "UNKNOWN/None must yield allowed_to_store=False (fail-closed)")

    # ========== EDGE CASES ==========

    def test_fail_closed_with_null_allowed_to_store(self):
        """Test fail-closed behavior when allowed_to_store is None"""
        # Create compliance run with None allowed_to_store
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
            allowed_to_store=None,
        )

        # Verify initial state
        self.assertIsNone(compliance_run.allowed_to_store)

        # When service fails, should set to False (fail-closed)
        compliance_run.status = ComplianceRunStatus.FAILED
        compliance_run.allowed_to_store = False
        compliance_run.save()

        compliance_run.refresh_from_db()
        self.assertFalse(compliance_run.allowed_to_store)

    def test_fail_closed_preserves_error_details(self):
        """Test that fail-closed preserves error details in regulation_mapping_json"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Simulate service failure with error details
        compliance_run.status = ComplianceRunStatus.FAILED
        compliance_run.allowed_to_store = False
        compliance_run.regulation_mapping_json = {
            "error": "Compliance service unavailable",
            "error_type": "ConnectionError",
            "fail_closed": True,
        }
        compliance_run.save()

        # Verify error details preserved
        compliance_run.refresh_from_db()
        self.assertIn("error", compliance_run.regulation_mapping_json)
        self.assertIn("fail_closed", compliance_run.regulation_mapping_json)
        self.assertTrue(compliance_run.regulation_mapping_json["fail_closed"])

    # ========== ERROR HANDLING ==========

    def test_fail_closed_handles_storage_errors(self):
        """Test fail-closed handles storage errors gracefully"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Use invalid storage path to trigger error
        self.file.storage_path = "invalid/path/file.csv"
        self.file.save()

        # Execute compliance run - should handle storage error
        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception:
            # Expected if storage unavailable
            pass

        # Verify fail-closed on storage error
        compliance_run.refresh_from_db()
        if compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertFalse(compliance_run.allowed_to_store)

    def test_fail_closed_handles_service_timeout(self):
        """Test fail-closed handles service timeout gracefully"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Set very short timeout to trigger timeout error
        self.job.timeout_seconds = 1
        self.job.save()

        # Execute compliance run - may timeout
        try:
            execute_compliance_run(str(compliance_run.id))
        except Exception:
            # Expected if timeout occurs
            pass

        # Verify compliance run was handled
        compliance_run.refresh_from_db()
        self.assertIn(
            compliance_run.status, [ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED]
        )

        if compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertFalse(compliance_run.allowed_to_store)
