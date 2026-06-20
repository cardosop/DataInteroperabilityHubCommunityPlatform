"""
Unit tests for DQ service client (critical path).

Tests use httpx.MockTransport to verify endpoint construction and request handling.
MockTransport is a test utility (not a mock object) that records requests for verification.
"""

import httpx
import pytest
from django.test import TestCase

from hub.apps.dq.service_client import DQServiceClient

pytestmark = pytest.mark.django_db(transaction=True)


class DQServiceClientTest(TestCase):
    """Test DQ service client (critical path for data quality)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = DQServiceClient()

    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self.client, "client") and self.client.client:
            self.client.client.close()

    def test_run_dq_success(self):
        """Test successful DQ run"""

        # Use MockTransport to verify endpoint construction and request handling
        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return success response"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "PASS",
                    "quality_score": 0.95,
                    "checks": [
                        {
                            "name": "expect_column_values_to_not_be_null",
                            "status": "PASS",
                            "result": {"observed_value": 100},
                        }
                    ],
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        result = self.client.run_dq(
            file_content=b"id,name\n1,Test", file_format="csv", profile_key="intake_basic_gx"
        )

        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["quality_score"], 0.95)

    def test_run_dq_with_failures(self):
        """Test DQ run with failures"""

        # Use MockTransport to verify endpoint construction and request handling
        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return failure response"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "FAIL",
                    "quality_score": 0.60,
                    "checks": [
                        {
                            "name": "expect_column_values_to_not_be_null",
                            "status": "FAIL",
                            "result": {"observed_value": 50, "expected_value": 100},
                        }
                    ],
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Use unique file content to avoid cache interference from other tests
        unique_content = b"id,name\n1,TestFailure\n2,AnotherFailure"

        result = self.client.run_dq(
            file_content=unique_content,
            file_format="csv",
            profile_key="intake_basic_gx",
            use_cache=False,  # Disable cache to avoid interference
        )

        self.assertEqual(result["overall_status"], "FAIL")
        self.assertEqual(result["quality_score"], 0.60)
        self.assertEqual(result["checks"][0]["status"], "FAIL")

    def test_run_dq_endpoint_construction(self):
        """Test that run_dq constructs endpoint correctly"""
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Record request and return mock response"""
            recorded_requests.append(request)
            return httpx.Response(
                200,
                json={"overall_status": "PASS", "quality_score": 0.95, "checks": []},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        self.client.run_dq(
            file_content=b"id,name\n1,Test", file_format="csv", profile_key="intake_basic_gx"
        )

        # Verify endpoint is '/run' (kebab-case)
        self.assertEqual(len(recorded_requests), 1)
        request = recorded_requests[0]
        self.assertEqual(request.url.path, "/run")
        self.assertEqual(request.method, "POST")

    def test_run_dq_http_error_handling(self):
        """Test DQ run handles HTTP errors gracefully"""

        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return error response"""
            return httpx.Response(500, json={"error": "Internal server error"}, request=request)

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Disable caching and circuit breaker fallback for this test
        # by directly calling the internal execute_dq_check function
        import hashlib

        from django.core.cache import cache

        cache_key = f"dq:run:{hashlib.sha256(b'id,name\n1,Test').hexdigest()}:intake_basic_gx"
        cache.delete(cache_key)  # Clear any cached result

        # Temporarily disable circuit breaker fallback by patching it
        original_call = self.client._circuit_breaker.call

        def call_without_fallback(func, fallback=None):
            return func()

        self.client._circuit_breaker.call = call_without_fallback

        try:
            with self.assertRaises(httpx.HTTPStatusError):
                self.client.run_dq(
                    file_content=b"id,name\n1,Test",
                    file_format="csv",
                    profile_key="intake_basic_gx",
                    use_cache=False,  # Disable caching
                )
        finally:
            self.client._circuit_breaker.call = original_call

    def test_run_dq_network_error_handling(self):
        """Test DQ run handles network errors gracefully"""

        def handler(request: httpx.Request) -> httpx.Response:
            """Simulate network error"""
            raise httpx.NetworkError("Connection refused")

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Disable caching and circuit breaker fallback for this test
        import hashlib

        from django.core.cache import cache

        cache_key = f"dq:run:{hashlib.sha256(b'id,name\n1,Test').hexdigest()}:intake_basic_gx"
        cache.delete(cache_key)  # Clear any cached result

        # Temporarily disable circuit breaker fallback by patching it
        original_call = self.client._circuit_breaker.call

        def call_without_fallback(func, fallback=None):
            return func()

        self.client._circuit_breaker.call = call_without_fallback

        try:
            with self.assertRaises(httpx.NetworkError):
                self.client.run_dq(
                    file_content=b"id,name\n1,Test",
                    file_format="csv",
                    profile_key="intake_basic_gx",
                    use_cache=False,  # Disable caching
                )
        finally:
            self.client._circuit_breaker.call = original_call

    def test_run_dq_invalid_file_format(self):
        """Test DQ run with invalid file format (edge case)"""

        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return error for invalid format"""
            return httpx.Response(
                400,
                json={"error": "Unsupported file format"},
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        # Disable caching and circuit breaker fallback for this test
        import hashlib

        from django.core.cache import cache

        cache_key = f"dq:run:{hashlib.sha256(b'invalid content').hexdigest()}:intake_basic_gx"
        cache.delete(cache_key)  # Clear any cached result

        # Temporarily disable circuit breaker fallback by patching it
        original_call = self.client._circuit_breaker.call

        def call_without_fallback(func, fallback=None):
            return func()

        self.client._circuit_breaker.call = call_without_fallback

        try:
            with self.assertRaises(httpx.HTTPStatusError):
                self.client.run_dq(
                    file_content=b"invalid content",
                    file_format="invalid_format",
                    profile_key="intake_basic_gx",
                    use_cache=False,  # Disable caching
                )
        finally:
            self.client._circuit_breaker.call = original_call

    def test_run_dq_empty_file_content(self):
        """Test DQ run with empty file content (edge case)"""

        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return response for empty file"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "WARN",
                    "quality_score": 0.0,
                    "checks": [
                        {
                            "name": "expect_file_not_empty",
                            "status": "FAIL",
                            "result": {"message": "File is empty"},
                        }
                    ],
                },
                request=request,
            )

        transport = httpx.MockTransport(handler)
        self.client.client = httpx.Client(transport=transport, base_url=self.client.base_url)

        result = self.client.run_dq(
            file_content=b"", file_format="csv", profile_key="intake_basic_gx"
        )

        self.assertEqual(result["overall_status"], "WARN")
        self.assertEqual(result["quality_score"], 0.0)
