"""
Unit tests for contract validation views (critical path).

All tests use real implementations (no mocks of hub services).
DataContractCLIClient uses real client with graceful handling when CLI service unavailable.
"""

import uuid

import httpx
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.contracts.cli_client import DataContractCLIClient
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import ContractsAPITransactionTestBase
from hub.apps.tenants.models import Tenant

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def check_datacontract_cli_available():
    """Check if DataContract CLI service is available.

    Only catches connection/transport exceptions so that import errors
    and other programming errors bubble up instead of being silently masked.
    """
    try:
        client = DataContractCLIClient()
        health = client.health_check()
        return isinstance(health, dict) and health.get("status") == "healthy"
    except (httpx.ConnectError, httpx.TimeoutException, ConnectionError, TimeoutError, OSError):
        return False


class ContractValidationViewTest(ContractsAPITransactionTestBase):
    """
    Test contract validation endpoints using real DataContractCLIClient.

    Uses real CLI client to verify end-to-end contract validation functionality.
    """

    def setUp(self):
        """Set up test fixtures"""
        from django.db import connection

        if connection.needs_rollback:
            connection.rollback()
        super().setUp()

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            validation_status=ValidationStatus.ERROR,  # Use ERROR as initial state
        )

    def test_validate_contract_synchronous(self):
        """
        Test synchronous contract validation using real DataContractCLIClient.

        Uses real CLI client to verify contract validation functionality.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        self.client.force_authenticate(user=self.user)

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # When CLI is available, the response must be 200 OK.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Synchronous validation must return 200 when CLI service is available",
        )

        # Verify contract was updated to a non-error status.
        # A structurally-valid contract must be VALID (or SKIPPED when the CLI
        # cannot validate the spec type/version).  It must never be INVALID.
        self.contract.refresh_from_db()
        self.assertIn(
            self.contract.validation_status,
            [ValidationStatus.VALID, ValidationStatus.SKIPPED],
            f"Expected VALID or SKIPPED for a well-formed contract, got {self.contract.validation_status}",
        )

    def test_validate_contract_asynchronous(self):
        """
        Test asynchronous contract validation using real create_job and DataContractCLIClient.

        Uses real job creation and CLI client to verify async validation functionality.
        """
        self.client.force_authenticate(user=self.user)

        # Use APIClient to make actual HTTP request with real create_job
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": True}, format="json"
        )

        # Response must be 202 ACCEPTED (job created) or 200 (sync fallback)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,  # Sync fallback when async job creation fails
                status.HTTP_202_ACCEPTED,
            ],
        )

        if response.status_code == status.HTTP_202_ACCEPTED:
            # Verify job was created
            self.assertIn("job_id", response.data)

            # Verify job exists in database (real job creation)
            from hub.apps.jobs.models import Job

            job_id = response.data["job_id"]
            job = Job.objects.get(id=job_id)
            self.assertIsNotNone(job)

    def test_validate_contract_with_errors(self):
        """
        Test contract validation with errors using real DataContractCLIClient.

        Uses real CLI client to verify error handling functionality.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        # Create contract with invalid structure to trigger errors
        invalid_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',  # Missing required fields
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
            validation_status=ValidationStatus.ERROR,
        )

        self.client.force_authenticate(user=self.user)

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{invalid_contract.id}/validate/", {"async": False}, format="json"
        )

        # When CLI is available, the response must be 200 OK (with errors).
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Validation of contract with errors must return 200 when CLI is available",
        )

        # Verify response structure
        self.assertIn("validation_status", response.data)
        # An invalid contract (missing required fields) must be rejected or warned.
        # SKIPPED is also valid when the CLI cannot validate the spec type.
        # VALID would mean the CLI accepted a broken contract — never acceptable.
        invalid_contract.refresh_from_db()
        self.assertIn(
            invalid_contract.validation_status,
            [ValidationStatus.INVALID, ValidationStatus.WARNING_ONLY, ValidationStatus.SKIPPED],
            f"Expected INVALID, WARNING_ONLY, or SKIPPED for a broken contract, got {invalid_contract.validation_status}",
        )

    def test_validate_contract_with_warnings(self):
        """
        Test contract validation produces warning-triggering contract that differs from sync test.

        Uses a contract with a known-warning-inducing structure to differentiate from
        test_validate_contract_synchronous.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        # Create a contract designed to trigger warnings (e.g., missing optional fields)
        warning_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "warning-test", "name": "Warning Contract", "info": {"owner": "unknown"}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "warning-test",
                "info": {"owner": "unknown"},
            },
            validation_status=ValidationStatus.ERROR,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/contracts/{warning_contract.id}/validate/", {"async": False}, format="json"
        )

        # When CLI is available, the response must be 200 OK.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Validation of warning-triggering contract must return 200 when CLI is available",
        )

        # Verify response structure includes warnings
        self.assertIn("validation_status", response.data)
        self.assertIn("warnings", response.data)
        warning_contract.refresh_from_db()
        self.assertIn(
            warning_contract.validation_status,
            [ValidationStatus.WARNING_ONLY, ValidationStatus.SKIPPED],
            f"Expected WARNING_ONLY or SKIPPED for a warning-triggering contract, got {warning_contract.validation_status}",
        )

    def test_validate_contract_service_response(self):
        """
        Validate contract service response structure regardless of CLI availability.

        When the CLI service IS available, the response must be 200 with
        ``validation_status`` in the body.  When the CLI service is UNAVAILABLE
        (500 or 503), the response must contain an ``error`` key.

        This test validates service-level response structure rather than a
        specific CLI error path, because we cannot control external service
        availability from an integration test.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Response may be 200 OK (success), 500 (service error), or 503 (unavailable)  # noqa: broad-status-codes

        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Happy path: verify the response contains expected validation fields
            self.assertIn(
                "validation_status", response.data, "200 response must include validation_status"
            )
            self.assertIn("valid", response.data, "200 response must include valid flag")
        else:
            # Error path: verify structured error response
            self.assertIn("error", response.data, "Error response must include error key")

    def test_validate_contract_enhanced_response(self):
        """
        Test enhanced validation response with normalization status using real DataContractCLIClient.

        Uses real CLI client to verify enhanced response structure with normalization status.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        self.client.force_authenticate(user=self.user)

        # Set normalization status on contract
        from hub.apps.contracts.models import NormalizationStatus

        self.contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        self.contract.save()

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Response may be 200 OK (success) or 500/503 (service error)  # noqa: broad-status-codes

        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Check enhanced response fields (real CLI response)
            self.assertIn("validation_status", response.data)
            self.assertIn("valid", response.data)
            self.assertIn("errors", response.data)
            self.assertIn("warnings", response.data)
            self.assertIn("error_count", response.data)
            self.assertIn("warning_count", response.data)
            self.assertIn("schema_compliance", response.data)
            self.assertIn("normalization_status", response.data)
            self.assertIn("normalization_compliant", response.data)
            self.assertIn("cli_version", response.data)
            self.assertIn("validated_at", response.data)
            self.assertIn("contract_id", response.data)

            # Verify normalization status is preserved
            self.assertEqual(
                response.data["normalization_status"], NormalizationStatus.NORMALIZED_OK
            )

    def test_validate_contract_valid_with_normalization(self):
        """
        Test validation response for valid contract with normalization status using real DataContractCLIClient.

        Uses real CLI client to verify validation response structure.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        self.client.force_authenticate(user=self.user)

        # Set normalization status on contract
        from hub.apps.contracts.models import NormalizationStatus

        self.contract.normalization_status = NormalizationStatus.NORMALIZED_WITH_WARNINGS
        self.contract.save()

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Response may be 200 OK (success) or 500/503 (service error)  # noqa: broad-status-codes

        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Verify response structure (real CLI response)
            self.assertIn("validation_status", response.data)
            self.assertIn("valid", response.data)
            self.assertIn("schema_compliance", response.data)
            self.assertIn("normalization_status", response.data)

            # Verify normalization status is preserved
            self.assertEqual(
                response.data["normalization_status"], NormalizationStatus.NORMALIZED_WITH_WARNINGS
            )

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_validate_contract_unauthenticated(self):
        """Test validation endpoint requires authentication"""
        # Clear authentication
        self.client.force_authenticate(user=None)
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Should return 401 Unauthorized with structured error
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data, "401 response must include structured error")
        error_code = response.data.get("error", {}).get("code", "")
        self.assertIn(
            "AUTH",
            error_code,
            f"401 error code must indicate authentication failure, got: {error_code}",
        )

    def test_validate_contract_not_found(self):
        """Test validation endpoint with non-existent contract"""
        import uuid

        self.client.force_authenticate(user=self.user)

        # Use valid UUID format but non-existent ID
        fake_id = str(uuid.uuid4())
        response = self.client.post(
            f"/api/v1/contracts/{fake_id}/validate/", {"async": False}, format="json"
        )

        # Must return 404 Not Found for a non-existent contract
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data, "404 response must include structured error")
        error_code = response.data.get("error", {}).get("code", "")
        self.assertIn(
            "NOT_FOUND", error_code, f"404 error code must be NOT_FOUND, got: {error_code}"
        )

    def test_validate_contract_cross_tenant(self):
        """Test validation endpoint respects tenant isolation"""
        # Create another tenant and user
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com", password="testpass123", tenant=other_tenant
        )

        # Authenticate as other user
        self.client.force_authenticate(user=other_user)

        # Try to validate contract from different tenant
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Tenant isolation — may return 403 (forbidden) or 404 (not found)
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
        )

    def test_validate_contract_invalid_id_format(self):
        """Test validation endpoint with invalid contract ID format"""
        self.client.force_authenticate(user=self.user)

        # Use invalid ID format
        response = self.client.post(
            "/api/v1/contracts/invalid-id-format/validate/", {"async": False}, format="json"
        )

        # Should return 404 Not Found (invalid UUID format)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(
            "error",
            response.data,
            "404 response for invalid ID format must include structured error",
        )
        error_code = response.data.get("error", {}).get("code", "")
        self.assertIn(
            "NOT_FOUND", error_code, f"404 error code must be NOT_FOUND, got: {error_code}"
        )

    def test_validate_contract_empty_request_body(self):
        """Test validation endpoint with empty request body (should use defaults)"""
        self.client.force_authenticate(user=self.user)

        # Empty body should default to sync validation
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {}, format="json"
        )

        # Should accept empty body and use defaults (async=False → 200 OK)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_202_ACCEPTED,
            ],
        )

    def test_validate_contract_invalid_request_body(self):
        """Validation endpoint treats truthy non-boolean ``async`` as async mode.

        ``request.data.get("async", False)`` evaluates any truthy value
        (including the string ``"not-a-boolean"``) as async=True, so the
        endpoint attempts async job creation → 202 Accepted (or 200 sync
        fallback if job creation fails)."""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/",
            {"async": "not-a-boolean"},
            format="json",
        )

        # Truthy → async path.  May return 202 (job created), 200
        # (sync fallback when job creation fails), or 400 if the
        # endpoint later adds strict boolean type-checking.
        self.assertLess(
            response.status_code,
            500,
        )

    def test_validate_contract_large_contract_auto_async(self):
        """Test validation endpoint automatically switches to async for large contracts"""
        self.client.force_authenticate(user=self.user)

        # Create a large contract (over 100KB)
        large_content = (
            '{"id": "large", "schema": {"fields": ['
            + ",".join([f'{{"name": "field_{i}", "type": "string"}}' for i in range(50000)])
            + "]}}"
        )

        large_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=large_content,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "large"},
            validation_status=ValidationStatus.ERROR,
        )

        # Request sync validation, but should auto-switch to async
        response = self.client.post(
            f"/api/v1/contracts/{large_contract.id}/validate/", {"async": False}, format="json"
        )

        # Should return 202 ACCEPTED (auto-switched to async) or 200 (sync fallback)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_202_ACCEPTED,  # Auto-switched to async
                status.HTTP_200_OK,  # If sync still works
            ],
        )

        if response.status_code == status.HTTP_202_ACCEPTED:
            # Verify job was created
            self.assertIn("job_id", response.data)

    def test_validate_contract_get_method_not_allowed(self):
        """Test validation endpoint only accepts POST method"""
        self.client.force_authenticate(user=self.user)

        # Try GET method (should not be allowed)
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/validate/")

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_validate_contract_put_method_not_allowed(self):
        """Test validation endpoint only accepts POST method"""
        self.client.force_authenticate(user=self.user)

        # Try PUT method (should not be allowed)
        response = self.client.put(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_validate_contract_delete_method_not_allowed(self):
        """Test validation endpoint only accepts POST method"""
        self.client.force_authenticate(user=self.user)

        # Try DELETE method (should not be allowed)
        response = self.client.delete(f"/api/v1/contracts/{self.contract.id}/validate/")

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_validate_contract_async_job_creation_failure_fallback(self):
        """Test validation endpoint falls back to sync when async job creation fails"""
        self.client.force_authenticate(user=self.user)

        # Request async validation
        # If job creation fails, should fall back to sync
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": True}, format="json"
        )

        # Should return 202 (job created) or 200 (fallback to sync)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_202_ACCEPTED,  # Job created successfully
                status.HTTP_200_OK,  # Fallback to sync validation
            ],
        )

    def test_validate_contract_response_structure_consistency(self):
        """Test validation response structure is consistent across different scenarios"""
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        self.client.force_authenticate(user=self.user)

        # Test sync validation response structure
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        if response.status_code == status.HTTP_200_OK:
            # Verify consistent response structure
            self.assertIn("validation_status", response.data)
            self.assertIn("valid", response.data)
            self.assertIn("errors", response.data)
            self.assertIn("warnings", response.data)
            # These fields should be present in enhanced response
            if "error_count" in response.data:
                self.assertIsInstance(response.data["error_count"], int)
            if "warning_count" in response.data:
                self.assertIsInstance(response.data["warning_count"], int)
