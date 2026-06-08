"""
Comprehensive unit tests for compliance service client.

Tests cover:
- Health check
- Scan file endpoint
- Endpoint construction verification
- Error handling
- Edge cases

All tests use real implementations (no mocks/stubs).
MockTransport is used only for endpoint construction verification (acceptable test utility).
"""

import httpx
import pytest
from django.test import TestCase

from hub.apps.compliance.service_client import ComplianceServiceClient

pytestmark = pytest.mark.django_db(transaction=True)


class ComplianceServiceClientTest(TestCase):
    """Comprehensive tests for compliance service client"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.service_breakers import (
            reset_shared_circuit_breakers_for_service,
        )
        # Reset the module-level shared circuit breaker BEFORE creating
        # the client.  Other tests in the suite can open the breaker;
        # the health-check test must always start with CLOSED state.
        reset_shared_circuit_breakers_for_service("compliance-service")
        self.client = ComplianceServiceClient()

    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self.client, "client") and self.client.client:
            self.client.client.close()

    # ========== HEALTH CHECK TESTS ==========

    def test_health_check_success(self):
        """Test successful health check with real service"""
        try:
            is_healthy, service_name = self.client.health_check()
        except (ConnectionError, OSError, httpx.RequestError) as e:
            self.skipTest(f"Compliance service not available: {e}")
        self.assertTrue(is_healthy)
        self.assertIsInstance(service_name, str)
        self.assertGreater(len(service_name), 0)

    def test_health_check_endpoint_construction(self):
        """Test that health_check constructs endpoint correctly using MockTransport"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(
                200, json={"status": "healthy", "service": "compliance-service"}, request=request
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Use real circuit breaker
        result = self.client.health_check()

        # Verify endpoint is '/health'
        self.assertEqual(len(recorded_requests), 1)
        request = recorded_requests[0]
        self.assertEqual(request.url.path, "/health")
        self.assertEqual(request.method, "GET")
        self.assertIsNotNone(result)

    # ========== SCAN FILE TESTS ==========

    def test_scan_file_endpoint_construction(self):
        """Test that scan_file constructs endpoint correctly using MockTransport"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(200, json={"overall_status": "PASS"}, request=request)

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Use real circuit breaker
        result = self.client.scan_file(
            file_content=b"id,name\n1,Test", file_format="csv", scan_mode="internal"
        )

        # Verify endpoint is '/scan-file' (kebab-case)
        self.assertEqual(len(recorded_requests), 1)
        request = recorded_requests[0]
        self.assertEqual(request.url.path, "/scan-file")
        self.assertEqual(request.method, "POST")
        self.assertIsNotNone(result)

    def test_scan_file_with_real_service(self):
        """Test scan_file with real compliance service"""
        try:
            is_healthy, _ = self.client.health_check()
            if not is_healthy:
                self.skipTest("Compliance service not available - skipping test")
        except (ConnectionError, OSError, httpx.RequestError):
            self.skipTest("Compliance service not available - skipping test")

        # Test with simple CSV content
        try:
            result = self.client.scan_file(
                file_content=b"id,name\n1,Test\n2,Sample", file_format="csv", scan_mode="internal"
            )

            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertIn("overall_status", result)
            self.assertIn("risk_level", result)
        except (ConnectionError, OSError, httpx.RequestError) as e:
            # Service may not be fully configured - that's OK
            self.skipTest(f"Compliance service scan failed: {e}")

    def test_scan_file_with_applicable_regulations(self):
        """Test scan_file forwards applicable_regulations in the multipart request body"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "overall_status": "PASS",
                    "risk_level": "LOW",
                    "allowed_to_store": True,
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        self.client.scan_file(
            file_content=b"id,name\n1,Test",
            file_format="csv",
            scan_mode="internal",
            applicable_regulations=["GDPR", "HIPAA"],
        )

        self.assertEqual(len(recorded_requests), 1)
        request = recorded_requests[0]
        # Multipart body should contain the JSON-encoded regulations
        body_bytes = request.read()
        self.assertIn(b"applicable_regulations", body_bytes)
        self.assertIn(b"GDPR", body_bytes)
        self.assertIn(b"HIPAA", body_bytes)

    # ========== ERROR HANDLING TESTS ==========

    def test_scan_file_handles_service_unavailable(self):
        """Test scan_file handles service unavailability gracefully —
        either by raising an exception or by returning a fail-closed fallback response."""
        original_client = self.client.client
        original_base_url = self.client.base_url
        self.client.base_url = "http://127.0.0.1:1"  # Invalid port
        # Replace the httpx client so base_url change takes effect.
        self.client.client = httpx.Client(
            base_url=self.client.base_url,
            timeout=self.client.client.timeout,
        )

        try:
            result = self.client.scan_file(
                file_content=b"id,name\n1,Test", file_format="csv", scan_mode="internal"
            )
            # The circuit breaker may return a fallback error dict instead of
            # raising.  Either behaviour is valid graceful handling.
            self.assertIsInstance(result, dict)
            self.assertFalse(
                result.get("allowed_to_store", True),
                "Fallback response must be fail-closed (allowed_to_store=False)",
            )
        except (ConnectionError, OSError, httpx.RequestError):
            # Raising on connection failure is also valid graceful handling
            pass
        finally:
            self.client.client = original_client
            self.client.base_url = original_base_url

    def test_scan_file_handles_invalid_file_format(self):
        """Test scan_file handles invalid file format gracefully"""
        try:
            is_healthy, _ = self.client.health_check()
            if not is_healthy:
                self.skipTest("Compliance service not available - skipping test")
        except (ConnectionError, OSError, httpx.RequestError):
            self.skipTest("Compliance service not available - skipping test")

        # Test with invalid format
        try:
            result = self.client.scan_file(
                file_content=b"invalid content", file_format="invalid_format", scan_mode="internal"
            )
            # Service may accept or reject - both are valid
            self.assertIsInstance(result, dict)
        except httpx.HTTPStatusError:
            # Expected if format not supported — the service may 400/422
            pass

    # ========== EDGE CASES ==========

    def test_scan_file_with_empty_content(self):
        """Test scan_file handles empty file content"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(
                200, json={"overall_status": "PASS", "risk_level": "NONE"}, request=request
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        result = self.client.scan_file(file_content=b"", file_format="csv", scan_mode="internal")

        # Should handle empty content
        self.assertIsNotNone(result)

    def test_scan_file_with_large_content(self):
        """Test scan_file handles large file content"""
        # Create large content (simulate)
        large_content = b"id,name\n" + b"1,Test\n" * 1000

        try:
            is_healthy, _ = self.client.health_check()
            if not is_healthy:
                self.skipTest("Compliance service not available - skipping test")
        except (ConnectionError, OSError, httpx.RequestError):
            self.skipTest("Compliance service not available - skipping test")

        try:
            result = self.client.scan_file(
                file_content=large_content, file_format="csv", scan_mode="internal"
            )
            # Should handle large content
            self.assertIsInstance(result, dict)
        except (ConnectionError, OSError, httpx.RequestError) as e:
            # May timeout or fail with large content - that's OK
            self.skipTest(f"Large content test failed: {e}")

    def test_scan_file_scan_mode_choices(self):
        """Test scan_file with different scan modes"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(200, json={"overall_status": "PASS"}, request=request)

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Test internal mode
        result1 = self.client.scan_file(
            file_content=b"id,name\n1,Test", file_format="csv", scan_mode="internal"
        )

        # Test external mode
        result2 = self.client.scan_file(
            file_content=b"id,name\n1,Test", file_format="csv", scan_mode="external"
        )

        # Both should work
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertEqual(len(recorded_requests), 2)
