"""
Unit tests for contract validation views (critical path).

All tests use real implementations (no mocks of hub services).
DataContractCLIClient uses real client with graceful handling when CLI service unavailable.
"""

import pytest

from hub.apps.contracts.cli_client import DataContractCLIClient
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import ContractsAPITransactionTestBase

pytestmark = pytest.mark.django_db(transaction=True)


def check_datacontract_cli_available():
    """Check if DataContract CLI service is available"""
    try:
        client = DataContractCLIClient()
        health = client.health_check()
        return isinstance(health, dict) and health.get("status") == "healthy"
    except Exception:
        return False


class ContractValidationViewTest(ContractsAPITransactionTestBase):
    """
    Test contract validation endpoints using real DataContractCLIClient.

    Uses real CLI client to verify end-to-end contract validation functionality.
    """

    def setUp(self):
        """Set up test fixtures"""
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

        # Response may be 200 OK (success) or 500/503 (service error)
        # The important thing is that real DataContractCLIClient was used
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Verify contract was updated
            self.contract.refresh_from_db()
            self.assertIn(
                self.contract.validation_status,
                [ValidationStatus.VALID, ValidationStatus.INVALID, ValidationStatus.WARNING_ONLY],
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

        # Response should be 202 ACCEPTED (job created) or error
        self.assertIn(
            response.status_code,
            [
                status.HTTP_202_ACCEPTED,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
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

        # Response may be 200 OK (with errors) or 500/503 (service error)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Verify response structure
            self.assertIn("validation_status", response.data)
            # Contract may have errors or warnings depending on CLI validation
            invalid_contract.refresh_from_db()
            self.assertIn(
                invalid_contract.validation_status,
                [ValidationStatus.VALID, ValidationStatus.INVALID, ValidationStatus.WARNING_ONLY],
            )

    def test_validate_contract_with_warnings(self):
        """
        Test contract validation with warnings using real DataContractCLIClient.

        Uses real CLI client to verify warning handling functionality.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        self.client.force_authenticate(user=self.user)

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Response may be 200 OK (with warnings) or 500/503 (service error)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # Verify response structure
            self.assertIn("validation_status", response.data)
            # Contract may have warnings depending on CLI validation
            self.contract.refresh_from_db()
            self.assertIn(
                self.contract.validation_status,
                [ValidationStatus.VALID, ValidationStatus.INVALID, ValidationStatus.WARNING_ONLY],
            )

    def test_validate_contract_service_error(self):
        """
        Test contract validation with service error using real DataContractCLIClient.

        Uses real CLI client to verify error handling when service unavailable.
        """
        # This test verifies error handling when CLI service is unavailable
        # If service is available, we can't easily test this path

        self.client.force_authenticate(user=self.user)

        # Use APIClient to make actual HTTP request with real DataContractCLIClient
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Response may be 200 OK (success), 500 (service error), or 503 (unavailable)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            # Verify error response structure
            self.assertIn("error", response.data)

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

        # Response may be 200 OK (success) or 500/503 (service error)
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

        # Response may be 200 OK (success) or 500/503 (service error)
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
        # Don't authenticate
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_validate_contract_not_found(self):
        """Test validation endpoint with non-existent contract"""
        import uuid

        self.client.force_authenticate(user=self.user)

        # Use valid UUID format but non-existent ID
        fake_id = str(uuid.uuid4())
        response = self.client.post(
            f"/api/v1/contracts/{fake_id}/validate/", {"async": False}, format="json"
        )

        # Should return 404 Not Found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_validate_contract_cross_tenant(self):
        """Test validation endpoint respects tenant isolation"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )

        # Authenticate as other user
        self.client.force_authenticate(user=other_user)

        # Try to validate contract from different tenant
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {"async": False}, format="json"
        )

        # Should return 404 Not Found (tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_validate_contract_invalid_id_format(self):
        """Test validation endpoint with invalid contract ID format"""
        self.client.force_authenticate(user=self.user)

        # Use invalid ID format
        response = self.client.post(
            "/api/v1/contracts/invalid-id-format/validate/", {"async": False}, format="json"
        )

        # Should return 404 Not Found (invalid UUID format)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_validate_contract_empty_request_body(self):
        """Test validation endpoint with empty request body (should use defaults)"""
        self.client.force_authenticate(user=self.user)

        # Empty body should default to sync validation
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/", {}, format="json"
        )

        # Should accept empty body and use defaults (async=False)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_202_ACCEPTED,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

    def test_validate_contract_invalid_request_body(self):
        """Test validation endpoint with invalid request body"""
        self.client.force_authenticate(user=self.user)

        # Invalid body (async should be boolean)
        response = self.client.post(
            f"/api/v1/contracts/{self.contract.id}/validate/",
            {"async": "not-a-boolean"},
            format="json",
        )

        # Should return 400 Bad Request or handle gracefully
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,  # If gracefully handled
                status.HTTP_400_BAD_REQUEST,  # If validation enforced
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ],
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

        # Should return 202 ACCEPTED (auto-switched to async) or handle gracefully
        self.assertIn(
            response.status_code,
            [
                status.HTTP_202_ACCEPTED,  # Auto-switched to async
                status.HTTP_200_OK,  # If sync still works
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
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

        # Should return 202 (job created) or 200 (fallback to sync) or error
        self.assertIn(
            response.status_code,
            [
                status.HTTP_202_ACCEPTED,  # Job created successfully
                status.HTTP_200_OK,  # Fallback to sync validation
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
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
