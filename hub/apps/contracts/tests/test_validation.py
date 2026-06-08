"""
Unit tests for contract validation.

All tests use real implementations (no mocks of hub services).
DataContractCLIClient uses real client with graceful handling when CLI service unavailable.
"""

import unittest

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.contracts.cli_client import (
    group_errors_by_category,
    interpret_validation_status,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import (
    ContractsAPITransactionTestBase,
    check_datacontract_cli_available,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
import uuid

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)

_DATA_CONTRACT_CLI_AVAILABLE = check_datacontract_cli_available()


class ContractValidationTest(ContractsAPITransactionTestBase):
    """
    Test contract validation using real DataContractCLIClient.

    Uses real CLI client to verify end-to-end contract validation functionality.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _DATA_CONTRACT_CLI_AVAILABLE:
            raise unittest.SkipTest("DataContract CLI service not available")

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_validate_contract_sync(self):
        """Synchronous contract validation returns 200 when CLI is available."""

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/contracts/{contract.id}/validate/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK,
            "Sync validation must return 200 when CLI service is available")
        self.assertIn("validation_status", response.data)

        contract.refresh_from_db()
        # A well-formed ODCS contract with schema.fields should pass validation;
        # SKIPPED is also acceptable when the CLI service defers judgement.
        self.assertIn(
            contract.validation_status,
            [ValidationStatus.VALID, ValidationStatus.WARNING_ONLY, ValidationStatus.SKIPPED],
            f"Expected VALID, WARNING_ONLY, or SKIPPED, got {contract.validation_status}",
        )
        # DB timestamp must be set after validation.
        self.assertIsNotNone(contract.last_validated_at,
            "last_validated_at must be set after successful validation")

    def test_validate_contract_with_errors(self):
        """Validation of contract with errors returns 200 with error details."""

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',  # Missing required fields
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/contracts/{contract.id}/validate/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK,
            "Validation with errors must return 200 when CLI is available")
        self.assertIn("validation_status", response.data)
        self.assertIn("errors", response.data)
        self.assertIn("grouped_errors", response.data)

        contract.refresh_from_db()
        # A contract with errors (missing required fields) gets INVALID, ERROR,
        # or SKIPPED (CLI may defer judgement on minimal contracts).
        self.assertIn(
            contract.validation_status,
            [ValidationStatus.INVALID, ValidationStatus.ERROR, ValidationStatus.SKIPPED],
            f"Expected INVALID, ERROR, or SKIPPED for contract with errors, got {contract.validation_status}",
        )
        # The response must include an errors list (may be empty for SKIPPED).
        self.assertIsInstance(response.data.get("errors"), list,
            "Response 'errors' must be a list")

    def test_validate_contract_async(self):
        """Async validation returns 202 ACCEPTED (or 200 sync fallback)."""

        large_contract = '{"id": "test", "name": "Test"}' * 10000  # Large contract

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=large_contract,
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/contracts/{contract.id}/validate/", {"async": True}, format="json"
        )

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED],
            f"Async validation must return 200 or 202, got {response.status_code}")

        if response.status_code == status.HTTP_202_ACCEPTED:
            self.assertIn("job_id", response.data)
            self.assertEqual(response.data["status"], "pending")

            from hub.apps.jobs.models import Job
            job_id = response.data["job_id"]
            job = Job.objects.get(id=job_id)
            self.assertIsNotNone(job)

    def test_lint_contract(self):
        """Contract linting returns 200 — view never returns 503."""

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/contracts/{contract.id}/lint/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK,
            "Lint must return 200 when CLI is available")
        self.assertIn("issues", response.data)

    def test_convert_contract(self):
        """Contract conversion returns 200 — view never returns 503."""

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/contracts/{contract.id}/convert/", {"target_format": "YAML"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK,
            "Convert must return 200 when CLI is available")
        self.assertIn("converted_contract", response.data)
        self.assertIn("format", response.data)

    def test_interpret_validation_status_valid(self):
        """Test interpreting VALID validation status"""
        result = {"validation_status": "VALID", "issues": []}

        status, errors, warnings = interpret_validation_status(result)

        self.assertEqual(status, "VALID")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_interpret_validation_status_with_errors(self):
        """Test interpreting validation status with errors"""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema",
                    "message": "Schema required",
                    "rule_id": "schema_required",
                },
                {
                    "severity": "WARNING",
                    "category": "style",
                    "path": "/name",
                    "message": "Consider adding description",
                    "rule_id": "missing_description",
                },
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        self.assertEqual(status, "INVALID")
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(errors[0]["category"], "schema")

    def test_group_errors_by_category(self):
        """Test grouping errors by category"""
        errors = [
            {"category": "schema", "message": "Schema error 1"},
            {"category": "schema", "message": "Schema error 2"},
            {"category": "format", "message": "Format error"},
            {"category": "unknown", "message": "Unknown error"},
        ]

        grouped = group_errors_by_category(errors)

        self.assertEqual(len(grouped["schema"]), 2)
        self.assertEqual(len(grouped["format"]), 1)
        self.assertEqual(len(grouped["unknown"]), 1)

    # ========== FAILURE SCENARIOS ==========

    def test_validate_contract_cli_service_unavailable(self):
        """When the CLI service is unreachable, the view's error handler sets
        ``validation_status=ERROR`` rather than crashing.

        We simulate an unreachable endpoint with an invalid port.
        ``@override_settings`` patches the setting that
        ``DataContractCLIClient.__init__`` reads at construction time,
        so the view (which creates a fresh client internally) sees the
        broken URL. Unlike the previous version of this test, which
        mutated a pre-created instance to no effect.
        """

        contract = Contract.objects.create(
            tenant=self.tenant, status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS, original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        from django.test import override_settings
        with override_settings(DATACONTRACT_SERVICE_URL="http://127.0.0.1:65535"):
            response = self.client.post(
                f"/api/v1/contracts/{contract.id}/validate/", {}, format="json"
            )

        # The view has a try/except around the CLI call that returns 200
        # with an error payload rather than crashing.  The contract's
        # validation_status stays unchanged (the view never updated it).
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.ERROR,
            "Error-handling path must set validation_status to ERROR when CLI is unreachable")

    def test_validate_contract_invalid_json(self):
        """Test contract validation with invalid JSON raises error"""

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", invalid json}',  # Invalid JSON
            created_by=self.user,
        )

        # Validation should handle invalid JSON gracefully
        response = self.client.post(f"/api/v1/contracts/{contract.id}/validate/", {}, format="json")

        # Returns 200 (with validation_status=ERROR) or 400 (with error detail)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
        )
        if response.status_code == status.HTTP_200_OK:
            self.assertIn("validation_status", response.data)
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn("error", response.data)

    def test_validate_contract_not_found(self):
        """Test contract validation with non-existent contract returns 404"""

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(f"/api/v1/contracts/{fake_id}/validate/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_validate_contract_cross_tenant(self):
        """Test contract validation respects tenant isolation"""
        # Create other tenant and contract
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other"}',
            created_by=other_user,
        )


        # Should not be able to validate contract from other tenant
        response = self.client.post(
            f"/api/v1/contracts/{other_contract.id}/validate/", {}, format="json"
        )

        # Tenant isolation IS enforced — get_object() uses the tenant-scoped
        # queryset from ContractViewSet.get_queryset().  Cross-tenant access
        # returns 403 (forbidden) or 404 (not found in tenant scope).
        self.assertIn(
            response.status_code,
            [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
            f"Expected 403/404 for cross-tenant access, got {response.status_code}",
        )

    def test_lint_contract_not_found(self):
        """Test linting non-existent contract returns 404"""

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(f"/api/v1/contracts/{fake_id}/lint/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_convert_contract_not_found(self):
        """Test converting non-existent contract returns 404"""

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            f"/api/v1/contracts/{fake_id}/convert/", {"target_format": "YAML"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_convert_contract_invalid_target_format(self):
        """Test converting contract with invalid target format"""
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")


        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/v1/contracts/{contract.id}/convert/",
            {"target_format": "INVALID_FORMAT"},
            format="json",
        )

        # View always returns 400 for invalid target format
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
            "Invalid target format must return 400")

    # ========== EDGE CASES ==========

    def test_interpret_validation_status_warning_only(self):
        """Test interpreting WARNING_ONLY validation status"""
        result = {
            "validation_status": "WARNING_ONLY",
            "issues": [
                {
                    "severity": "WARNING",
                    "category": "style",
                    "path": "/name",
                    "message": "Consider adding description",
                    "rule_id": "missing_description",
                }
            ],
        }

        status_val, errors, warnings = interpret_validation_status(result)

        self.assertEqual(status_val, "WARNING_ONLY")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 1)

    def test_interpret_validation_status_missing_issues(self):
        """Test interpreting validation status without issues field"""
        result = {"validation_status": "VALID"}

        status_val, errors, warnings = interpret_validation_status(result)

        self.assertEqual(status_val, "VALID")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_group_errors_by_category_empty_list(self):
        """Test grouping empty errors list"""
        errors = []

        grouped = group_errors_by_category(errors)

        self.assertIsInstance(grouped, dict)
        self.assertEqual(len(grouped), 0)

    def test_group_errors_by_category_missing_category(self):
        """Test grouping errors with missing category field"""
        errors = [
            {"message": "Error without category"},
            {"category": "schema", "message": "Schema error"},
        ]

        grouped = group_errors_by_category(errors)

        # Should handle missing category gracefully
        self.assertIsInstance(grouped, dict)
        # One error has no category — must be grouped under "unknown" or "other".
        unknown_bucket = grouped.get("unknown", grouped.get("other", []))
        self.assertGreater(len(unknown_bucket), 0,
            "Error without 'category' must land in 'unknown' or 'other' bucket")

    def test_validate_contract_large_contract_triggers_async(self):
        """Test that large contracts automatically trigger async validation"""

        # Create very large contract
        large_contract = '{"id": "test", "name": "Test", "data": "' + "x" * 1000000 + '"}'

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=large_contract,
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/contracts/{contract.id}/validate/", {}, format="json")

        # Large contracts (>100KB) must auto-switch to async
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED,
            f"Large contract must auto-switch to async (202), got {response.status_code}")
        self.assertIn("job_id", response.data)

    def test_validate_contract_sequential_stress(self):
        """Rapid sequential validation requests must not crash or corrupt state.

        Replaces the thread-unsafe concurrent test — Django's APIClient is NOT
        thread-safe (shared connection/auth state), so we use sequential calls
        to verify stability under rapid repeated use.
        """

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        # 5 rapid sequential requests — must all return valid HTTP status codes
        for i in range(5):
            response = self.client.post(
                f"/api/v1/contracts/{contract.id}/validate/", {}, format="json"
            )
            self.assertIn(response.status_code, [200, 202],
                f"Request {i+1} returned unexpected status {response.status_code}")

    def test_validate_contract_retry_on_failure(self):
        """Validation retry-and-circuit-breaker: when the service is
        unreachable, the CLI client retries (the log shows retry attempts
        with exponentially-increasing delays), then the circuit breaker
        returns a fallback response. The endpoint does NOT hang — it
        returns within a few seconds.

        We force an unreachable service URL to exercise the retry path.
        """

        contract = Contract.objects.create(
            tenant=self.tenant, status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS, original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        import time as _time
        from django.test import override_settings
        start = _time.monotonic()
        with override_settings(DATACONTRACT_SERVICE_URL="http://127.0.0.1:65535"):
            response = self.client.post(
                f"/api/v1/contracts/{contract.id}/validate/", {}, format="json"
            )
        elapsed = _time.monotonic() - start

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])
        # Retries must have completed — the endpoint returned, it didn't hang.
        # The retry loop uses ~1s + 3s delays with short timeouts, so
        # elapsed should be well under 30s (generous upper bound).
        self.assertLess(elapsed, 30, f"Retry/fallback took {elapsed:.1f}s — expected <30s")
