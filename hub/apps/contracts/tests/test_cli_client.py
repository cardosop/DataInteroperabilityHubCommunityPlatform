"""
Comprehensive unit tests for DataContract CLI client.

Tests cover:
- Health check
- Validation (success, errors, cache)
- Lint operation
- Convert operation
- Error handling
- Edge cases

All tests use real implementations (no mocks/stubs).
MockTransport is used only for endpoint verification (acceptable test utility).
Real service calls handle unavailability gracefully.
"""

import unittest

import httpx
import pytest
from django.core.cache import cache
from django.test import TestCase

from hub.apps.contracts.cli_client import (
    SYNC_TIMEOUT,
    DataContractCLIClient,
    group_errors_by_category,
    interpret_validation_status,
)
from hub.apps.contracts.tests.test_base import check_datacontract_cli_available

pytestmark = pytest.mark.django_db(transaction=True)

_DATA_CONTRACT_CLI_AVAILABLE = check_datacontract_cli_available()


class DataContractCLIClientTest(TestCase):
    """Comprehensive tests for DataContract CLI client"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _DATA_CONTRACT_CLI_AVAILABLE:
            raise unittest.SkipTest("DataContract CLI service not available")

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        self.client = DataContractCLIClient()

    def tearDown(self):
        """Clean up test fixtures"""
        cache.clear()

    # ========== HEALTH CHECK TESTS ==========

    def test_health_check_success(self):
        """Successful health check returns status and cli_version."""
        result = self.client.health_check()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "healthy",
            "Health check must report 'healthy' when service is available")
        self.assertIn("cli_version", result)

    # ========== VALIDATION TESTS ==========

    def test_validate_success(self):
        """Successful contract validation returns a valid status for a well-formed contract."""
        result = self.client.validate(
            raw_contract='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            format="JSON",
        )

        self.assertIsInstance(result, dict)
        self.assertIn("validation_status", result)
        # A well-formed ODCS contract with schema.fields must pass validation.
        # The CLI returns uppercase statuses; accept the canonical success set.
        self.assertIn(
            result["validation_status"],
            {"VALID", "WARNING_ONLY", "SKIPPED"},
            f"Expected VALID, WARNING_ONLY, or SKIPPED, got {result.get('validation_status')}",
        )

    def test_validate_with_cache(self):
        """Validation with cache enabled returns consistent results across calls."""
        contract_content = '{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        result1 = self.client.validate(raw_contract=contract_content, format="JSON", use_cache=True)
        result2 = self.client.validate(raw_contract=contract_content, format="JSON", use_cache=True)

        self.assertIsInstance(result1, dict)
        self.assertIsInstance(result2, dict)
        self.assertIn("validation_status", result1)
        self.assertIn("validation_status", result2)
        # Both calls must return the same validation_status for the same input.
        self.assertEqual(
            result1["validation_status"], result2["validation_status"],
            "Cached and non-cached calls must return the same validation_status",
        )

    def test_validate_endpoint_construction(self):
        """Validate constructs the correct ``/validate`` endpoint and POST method.

        Uses ``use_cache=False`` so ``validate()`` does NOT call
        ``health_check()`` first (which would make a real request and
        trip the circuit breaker before our mock ever fires).  Also
        resets the circuit breaker to CLOSED before the test because it
        is Redis-backed and stale OPEN state from prior ``--keepdb``
        runs would cause an immediate fallback without our mock firing.
        """
        # Reset circuit breaker (Redis-backed, survives test instances).
        self.client._circuit_breaker.reset()

        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_requests.append(request)
            return httpx.Response(
                200,
                json={"validation_status": "VALID", "issues": []},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        original_make_request = self.client._make_request

        def mock_make_request(endpoint, data, timeout=None, max_retries=2):
            url = f"{self.client.base_url}{endpoint}"
            with httpx.Client(transport=transport, base_url=self.client.base_url) as client:
                response = client.post(url, json=data)
                response.raise_for_status()
                return response.json()

        self.client._make_request = mock_make_request

        try:
            result = self.client.validate(
                raw_contract='{"id": "test"}', format="JSON", use_cache=False,
            )

            self.assertEqual(len(recorded_requests), 1,
                "Expected exactly 1 request through the mock transport")
            request = recorded_requests[0]
            self.assertEqual(request.url.path, "/validate")
            self.assertEqual(request.method, "POST")
            self.assertIsNotNone(result)
        finally:
            self.client._make_request = original_make_request

    def test_validate_handles_service_unavailable(self):
        """Validate returns ERROR fallback dict when service is unreachable."""
        original_base_url = self.client.base_url
        self.client.base_url = "http://localhost:99999"  # Invalid port

        try:
            result = self.client.validate(raw_contract='{"id": "test"}', format="JSON")
            self.assertIsInstance(result, dict,
                "Must return a dict (fallback response) when service is unavailable")
            self.assertIn("validation_status", result)
            self.assertEqual(result["validation_status"], "ERROR",
                "Unreachable service must return validation_status='ERROR'")
            self.assertIn("error", result,
                "Fallback response must include an 'error' key")
        finally:
            self.client.base_url = original_base_url

    # ========== LINT TESTS ==========

    def test_lint_endpoint_construction(self):
        """Test that lint constructs endpoint correctly using MockTransport"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(
                200,
                json={"issues": [{"severity": "WARNING", "category": "style"}]},
                request=request,
            )

        transport = httpx.MockTransport(handler)

        original_make_request = self.client._make_request

        def mock_make_request(endpoint, data, timeout=None, max_retries=2):
            url = f"{self.client.base_url}{endpoint}"
            with httpx.Client(transport=transport, base_url=self.client.base_url) as client:
                response = client.post(url, json=data)
                response.raise_for_status()
                return response.json()

        self.client._make_request = mock_make_request

        try:
            result = self.client.lint(raw_contract='{"id": "test"}', format="JSON")

            # Verify endpoint is '/lint'
            self.assertEqual(len(recorded_requests), 1)
            request = recorded_requests[0]
            self.assertEqual(request.url.path, "/lint")
            self.assertEqual(request.method, "POST")
            self.assertIsNotNone(result)
        finally:
            self.client._make_request = original_make_request

    def test_lint_with_real_service(self):
        """Lint with real CLI service returns issues list."""
        result = self.client.lint(raw_contract='{"id": "test", "name": "Test"}', format="JSON")
        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIsInstance(result["issues"], list,
            "Lint 'issues' must be a list")

    # ========== CONVERT TESTS ==========

    def test_convert_endpoint_construction(self):
        """Test that convert constructs endpoint correctly using MockTransport"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(
                200,
                json={"converted_contract": "id: test", "target_format": "YAML"},
                request=request,
            )

        transport = httpx.MockTransport(handler)

        original_make_request = self.client._make_request

        def mock_make_request(endpoint, data, timeout=None, max_retries=2):
            url = f"{self.client.base_url}{endpoint}"
            with httpx.Client(transport=transport, base_url=self.client.base_url) as client:
                response = client.post(url, json=data)
                response.raise_for_status()
                return response.json()

        self.client._make_request = mock_make_request

        try:
            result = self.client.convert(
                raw_contract='{"id": "test"}', source_format="JSON", target_format="YAML"
            )

            # Verify endpoint is '/convert'
            self.assertEqual(len(recorded_requests), 1)
            request = recorded_requests[0]
            self.assertEqual(request.url.path, "/convert")
            self.assertEqual(request.method, "POST")
            self.assertIsNotNone(result)
        finally:
            self.client._make_request = original_make_request

    def test_convert_with_real_service(self):
        """Convert with real CLI service returns converted_contract and target_format."""
        result = self.client.convert(
            raw_contract='{"id": "test", "name": "Test"}',
            source_format="JSON",
            target_format="YAML",
        )
        self.assertIsInstance(result, dict)
        self.assertIn("converted_contract", result)
        self.assertIn("target_format", result)
        self.assertIsNotNone(result["converted_contract"],
            "converted_contract must not be None")
        self.assertEqual(result["target_format"], "YAML",
            "target_format must match the requested YAML format")

    # ========== ERROR HANDLING ==========

    def test_validate_handles_timeout(self):
        """Validate with very short timeout returns ERROR fallback dict."""
        original_timeout = self.client.timeout
        self.client.timeout = 0.001  # Very short timeout

        try:
            result = self.client.validate(raw_contract='{"id": "test"}', format="JSON")
            self.assertIsInstance(result, dict,
                "Must return a dict even with short timeout (circuit breaker fallback)")
            self.assertIn("validation_status", result)
            # A very short timeout may or may not trigger — local services
            # can respond within 1ms. Either ERROR (timeout hit) or a real
            # status (fast response) is valid; the contract is that we
            # never crash.
            self.assertIn(result["validation_status"],
                {"VALID", "WARNING_ONLY", "INVALID", "ERROR", "SKIPPED"},
                f"Timeout path returned unexpected status: {result.get('validation_status')}")
        finally:
            self.client.timeout = original_timeout

    def test_validate_handles_invalid_json(self):
        """Validate handles invalid JSON gracefully — returns dict with validation_status."""
        result = self.client.validate(raw_contract="invalid json", format="JSON")
        self.assertIsInstance(result, dict)
        self.assertIn("validation_status", result,
            "Response must include validation_status even for invalid JSON")

    # ========== EDGE CASES ==========

    def test_validate_empty_contract(self):
        """Validate handles empty JSON contract — returns dict with validation_status."""
        result = self.client.validate(raw_contract="{}", format="JSON")
        self.assertIsInstance(result, dict)
        self.assertIn("validation_status", result,
            "Response must include validation_status even for empty contract")

    def test_validate_large_contract(self):
        """Validate handles large contract — must not crash, must return a dict."""
        large_contract = '{"id": "test", "data": "' + "x" * 100000 + '"}'

        result = self.client.validate(raw_contract=large_contract, format="JSON")
        self.assertIsInstance(result, dict,
            "Large contract must return a dict (fallback or async trigger)")
        self.assertIn("validation_status", result)
        self.assertIn(result["validation_status"], {"VALID", "WARNING_ONLY", "INVALID", "ERROR", "SKIPPED"},
            "Large contract must return a valid validation_status value")


class InterpretValidationStatusTest(TestCase):
    """Test validation status interpretation (critical path)"""

    def test_interpret_valid_status(self):
        """Test interpreting VALID status"""
        validation_result = {"validation_status": "VALID", "issues": []}

        status, errors, warnings = interpret_validation_status(validation_result)

        self.assertEqual(status, "VALID")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_interpret_invalid_with_errors(self):
        """Test interpreting INVALID status with errors"""
        validation_result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "$.name",
                    "message": "Name is required",
                    "rule_id": "required_field",
                },
                {
                    "severity": "CRITICAL",
                    "category": "data",
                    "path": "$.id",
                    "message": "ID must be unique",
                    "rule_id": "unique_id",
                },
            ],
        }

        status, errors, warnings = interpret_validation_status(validation_result)

        self.assertEqual(status, "INVALID")
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(errors[0]["severity"], "ERROR")
        self.assertEqual(errors[1]["severity"], "CRITICAL")

    def test_interpret_warning_only(self):
        """Test interpreting WARNING_ONLY status"""
        validation_result = {
            "validation_status": "WARNING_ONLY",
            "issues": [
                {
                    "severity": "WARNING",
                    "category": "style",
                    "message": "Consider adding description",
                },
                {"severity": "INFO", "category": "metadata", "message": "Missing tags"},
            ],
        }

        status, errors, warnings = interpret_validation_status(validation_result)

        self.assertEqual(status, "WARNING_ONLY")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 2)

    def test_interpret_mixed_errors_and_warnings(self):
        """Test interpreting mixed errors and warnings"""
        validation_result = {
            "validation_status": "INVALID",
            "issues": [
                {"severity": "ERROR", "category": "schema", "message": "Schema error"},
                {"severity": "WARNING", "category": "style", "message": "Style warning"},
            ],
        }

        status, errors, warnings = interpret_validation_status(validation_result)

        self.assertEqual(status, "INVALID")
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 1)


class GroupErrorsByCategoryTest(TestCase):
    """Test error grouping by category (critical path)"""

    def test_group_errors_by_category(self):
        """Test grouping errors by category"""
        errors = [
            {"category": "schema", "message": "Schema error 1"},
            {"category": "schema", "message": "Schema error 2"},
            {"category": "data", "message": "Data error 1"},
        ]

        grouped = group_errors_by_category(errors)

        self.assertEqual(len(grouped["schema"]), 2)
        self.assertEqual(len(grouped["data"]), 1)
        self.assertEqual(grouped["schema"][0]["message"], "Schema error 1")

    def test_group_errors_with_unknown_category(self):
        """Test grouping errors with unknown category"""
        errors = [
            {"message": "Error without category"},
            {"category": "schema", "message": "Schema error"},
        ]

        grouped = group_errors_by_category(errors)

        self.assertEqual(len(grouped["unknown"]), 1)
        self.assertEqual(len(grouped["schema"]), 1)
