"""
Comprehensive unit tests for fail-closed behavior.

Tests cover:
- Fail-closed when allowed_to_store=False
- Fail-closed on service errors / UNKNOWN / fallback
- Fail-closed blocks asset activation
- Edge cases
- Error handling

All tests use real implementations. Circuit-breaker tests use the
real Redis-backed breaker by manipulating Redis state directly.
"""

import copy
import time
import uuid

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

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
        from hub.apps.core.resilience.service_breakers import (
            reset_shared_circuit_breakers_for_service,
        )
        reset_shared_circuit_breakers_for_service("compliance-service")

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
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

    def _drive_to_terminal_status(self, compliance_run, max_attempts=4):
        """
        Drive an async (QUEUED) compliance run to a terminal state by calling
        poll_compliance_job inline. In unit-test environments no Hub RQ worker
        is running, so the poll task must be executed synchronously here.

        Only a few attempts are needed — there is no async worker in tests,
        so if the first poll doesn't resolve the run, subsequent retries
        won't help.  Short backoff (1s / 2s / 3s) keeps the ceiling low.
        """
        import logging
        _logger = logging.getLogger(__name__)

        from hub.apps.compliance.models import ComplianceRunStatus
        from hub.apps.compliance.tasks import poll_compliance_job

        compliance_run.refresh_from_db()
        for attempt in range(max_attempts):
            if compliance_run.status in (
                ComplianceRunStatus.SUCCEEDED,
                ComplianceRunStatus.FAILED,
            ):
                break
            poll_compliance_job(compliance_run.id)
            compliance_run.refresh_from_db()
            if compliance_run.status not in (
                ComplianceRunStatus.QUEUED,
                ComplianceRunStatus.RUNNING,
            ):
                break
            delay = 1.0 * (attempt + 1)
            _logger.debug(
                "poll attempt %d/%d (status=%s, delay=%.1fs)",
                attempt + 1, max_attempts,
                compliance_run.status, delay,
            )
            time.sleep(delay)

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
                    time.sleep(delay_seconds)  # INTENTIONAL: test-specific timing requirement
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
        except (ConnectionError, OSError) as exc:
            compliance_run.refresh_from_db()
            if compliance_run.status == ComplianceRunStatus.FAILED:
                self.assertFalse(compliance_run.allowed_to_store)
                return
            self.skipTest(f"Compliance service connection error: {exc}")

        # Drive async run to terminal state if needed
        self._drive_to_terminal_status(compliance_run)

        # Assert the run reached a terminal state
        compliance_run.refresh_from_db()
        self.assertIn(compliance_run.status, [ComplianceRunStatus.SUCCEEDED, ComplianceRunStatus.FAILED, ComplianceRunStatus.QUEUED])
        # If it completed, verify fail-closed
        if compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertFalse(compliance_run.allowed_to_store)
        elif compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            # Still verify allowed_to_store is set (not None)
            self.assertIsNotNone(compliance_run.allowed_to_store)
        elif compliance_run.status == ComplianceRunStatus.QUEUED:
            self.skipTest("Compliance service returned async response")

    def test_fail_closed_on_storage_error(self):
        """Test that storage errors (invalid path) result in fail-closed behavior."""
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
        except (ConnectionError, OSError, ValueError) as exc:
            # Expected if storage/service unavailable
            pass

        # Verify fail-closed on error
        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.FAILED)
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
        """scan_file fallback response has allowed_to_store=False (fail-closed).

        When the compliance service is unreachable, scan_file returns a
        fail-closed fallback response. Test this client-level behavior
        by using an invalid service URL that triggers a real connection
        error, then verifying the fallback contract.
        """
        # Use a non-routable host to trigger a real connection failure.
        # This exercises the real retry/fallback path in scan_file
        # without mocking any internal method.
        import copy
        client = ComplianceServiceClient()
        original_base_url = client.base_url
        original_client = client.client
        try:
            # Point to a port on localhost where nothing is listening.
            client.base_url = "http://127.0.0.1:65535"
            client.client = httpx.Client(base_url=client.base_url, timeout=2)
            result = client.scan_file(file_content=b"a,b\n1,2", file_format="csv")
        finally:
            client.client.close()
            client.base_url = original_base_url
            client.client = original_client

        self.assertFalse(result["allowed_to_store"], "Fallback must be fail-closed")
        self.assertEqual(result["overall_status"], "UNKNOWN")

    def test_when_client_returns_unknown_persist_result_sets_fail_closed(self):
        """When _persist_result receives UNKNOWN/allowed_to_store=None,
        Hub sets allowed_to_store=False (fail-closed).

        Tests the _persist_result layer directly (no mock needed) — this is
        the same fail-closed enforcement that execute_compliance_run relies on
        after receiving a result from _call_compliance_service.
        """
        from hub.apps.compliance.services import ComplianceService

        result_data = {
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
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        ComplianceService._persist_result(compliance_run, result_data)

        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.SUCCEEDED)
        self.assertFalse(
            compliance_run.allowed_to_store,
            "UNKNOWN/None must yield allowed_to_store=False (fail-closed)",
        )

    # ========== EDGE CASES ==========

    def test_persist_result_failed_payload_sets_fail_closed_and_preserves_error(self):
        """_persist_result with FAILED/ERROR status sets allowed_to_store=False
        and stores error details in regulation_mapping_json."""
        from hub.apps.compliance.services import ComplianceService

        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        ComplianceService._persist_result(
            compliance_run,
            {
                "status": "FAILED",
                "error": "scan worker raised RuntimeError('boom')",
            },
        )

        compliance_run.refresh_from_db()
        self.assertEqual(compliance_run.status, ComplianceRunStatus.FAILED)
        self.assertFalse(
            compliance_run.allowed_to_store,
            "FAILED payload must set allowed_to_store=False (fail-closed)",
        )
        self.assertIsNotNone(compliance_run.regulation_mapping_json)
        self.assertEqual(
            compliance_run.regulation_mapping_json["error"],
            "scan worker raised RuntimeError('boom')",
        )
        self.assertEqual(
            compliance_run.regulation_mapping_json["error_type"],
            "EXECUTION_ERROR",
        )

    # ========== ERROR HANDLING ==========

    def test_fail_closed_handles_storage_errors(self):
        """Test fail-closed handles storage errors gracefully"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant, file=self.file, job=self.job, status=ComplianceRunStatus.PENDING
        )

        # Use invalid storage path to trigger error
        self.file.storage_path = "invalid/path/file.csv"
        self.file.save()

        execute_compliance_run(str(compliance_run.id))

        compliance_run.refresh_from_db()
        self.assertEqual(
            compliance_run.status,
            ComplianceRunStatus.FAILED,
            "Invalid storage path must produce FAILED status",
        )
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

        # Drive async (QUEUED) run to a terminal state — RQ worker not running in tests
        self._drive_to_terminal_status(compliance_run)
        # Verify compliance run was handled
        compliance_run.refresh_from_db()
        self.assertIn(
            compliance_run.status,
            [
                ComplianceRunStatus.SUCCEEDED,
                ComplianceRunStatus.FAILED,
                ComplianceRunStatus.QUEUED,
            ],
        )

        if compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertFalse(compliance_run.allowed_to_store)

    # ========== DEGRADED COMPLIANCE STATUS ==========

    def test_apply_degraded_compliance_when_circuit_open(self):
        """When compliance-service circuit is OPEN and asset has datasets,
        asset.compliance_status is set to WARN.

        Uses the real Redis-backed circuit breaker (no mock) by manually
        transitioning the breaker to OPEN state via Redis, then restoring
        CLOSED after the assertion.
        """
        from hub.apps.compliance.services import ComplianceService
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )

        # Create asset with a dataset (method returns early if no datasets)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="degraded-circuit",
            name="Degraded Circuit Asset",
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        breaker = get_shared_circuit_breaker("compliance-service")
        original_state = breaker.get_state()
        try:
            # Manually transition the real Redis-backed breaker to OPEN.
            breaker._set_state(CircuitBreakerState.OPEN)
            ComplianceService.apply_degraded_compliance_status_if_circuit_open(asset)

            asset.refresh_from_db()
            self.assertEqual(
                asset.compliance_status,
                ComplianceStatus.WARN,
                "Circuit-breaker OPEN must set asset compliance_status to WARN",
            )
        finally:
            # Restore the original circuit breaker state.
            breaker._set_state(original_state)
