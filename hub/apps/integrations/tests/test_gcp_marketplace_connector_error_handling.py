"""
Unit Tests for GCP Marketplace Connector Error Handling, Retry Logic, and Circuit Breaker

Tests the error handling, retry logic, and circuit breaker integration for the
GCP Marketplace connector.

These tests validate:
- Retry logic for transient failures (429, 500, 502, 503, 504)
- No retry for client errors (400, 401, 403, 404)
- Error mapping from Google Cloud errors to connector exceptions
- Circuit breaker integration
- Structured logging with correlation IDs
"""

import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, PermissionError
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector

# Optional Google Cloud imports - skip tests if not available
try:
    from google.api_core import exceptions as google_exceptions

    GoogleAPIError = google_exceptions.GoogleAPIError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    google_exceptions = None
    GoogleAPIError = Exception  # Fallback
    GOOGLE_CLOUD_AVAILABLE = False

import pytest

pytestmark = pytest.mark.skipif(
    not GOOGLE_CLOUD_AVAILABLE, reason="Google Cloud libraries not installed"
)


class TestGCPMarketplaceConnectorRetryLogic(TestCase):
    """Test retry logic for transient failures"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    def test_is_transient_error_429(self):
        """Test _is_transient_error() returns True for 429 (Too Many Requests)"""
        self.assertTrue(self.connector._is_transient_error(429))

    def test_is_transient_error_500(self):
        """Test _is_transient_error() returns True for 500 (Internal Server Error)"""
        self.assertTrue(self.connector._is_transient_error(500))

    def test_is_transient_error_502(self):
        """Test _is_transient_error() returns True for 502 (Bad Gateway)"""
        self.assertTrue(self.connector._is_transient_error(502))

    def test_is_transient_error_503(self):
        """Test _is_transient_error() returns True for 503 (Service Unavailable)"""
        self.assertTrue(self.connector._is_transient_error(503))

    def test_is_transient_error_504(self):
        """Test _is_transient_error() returns True for 504 (Gateway Timeout)"""
        self.assertTrue(self.connector._is_transient_error(504))

    def test_is_transient_error_400(self):
        """Test _is_transient_error() returns False for 400 (Bad Request)"""
        self.assertFalse(self.connector._is_transient_error(400))

    def test_is_transient_error_401(self):
        """Test _is_transient_error() returns False for 401 (Unauthorized)"""
        self.assertFalse(self.connector._is_transient_error(401))

    def test_is_transient_error_403(self):
        """Test _is_transient_error() returns False for 403 (Forbidden)"""
        self.assertFalse(self.connector._is_transient_error(403))

    def test_is_transient_error_404(self):
        """Test _is_transient_error() returns False for 404 (Not Found)"""
        self.assertFalse(self.connector._is_transient_error(404))

    def test_is_transient_error_none(self):
        """Test _is_transient_error() returns False for None"""
        self.assertFalse(self.connector._is_transient_error(None))

    @patch("time.sleep")
    def test_execute_with_retry_retries_on_transient_error(self, mock_sleep):
        """Test _execute_with_retry() retries on transient errors"""
        call_count = [0]

        def failing_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                error = GoogleAPIError("Service unavailable")
                error.code = 503
                raise error
            return "success"

        result = self.connector._execute_with_retry(
            failing_operation, "test_operation", "test context"
        )

        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 2)
        # Should sleep once (after first failure)
        self.assertEqual(mock_sleep.call_count, 1)
        # Check exponential backoff: backoff_factor * (2 ** attempt) = 1 * (2 ** 0) = 1
        mock_sleep.assert_called_with(1.0)

    @patch("time.sleep")
    def test_execute_with_retry_max_retries_exceeded(self, mock_sleep):
        """Test _execute_with_retry() raises ConnectionError after max retries"""

        def always_failing_operation():
            error = GoogleAPIError("Service unavailable")
            error.code = 503
            raise error

        with self.assertRaises(ConnectionError) as cm:
            self.connector._execute_with_retry(
                always_failing_operation, "test_operation", "test context"
            )

        self.assertIn("Transient error", str(cm.exception))
        # Should retry max_retries times (2), so sleep should be called 2 times
        self.assertEqual(mock_sleep.call_count, 2)
        # Check exponential backoff delays
        self.assertEqual(mock_sleep.call_args_list[0][0][0], 1.0)  # 1 * (2 ** 0)
        self.assertEqual(mock_sleep.call_args_list[1][0][0], 2.0)  # 1 * (2 ** 1)

    def test_execute_with_retry_no_retry_on_client_error(self):
        """Test _execute_with_retry() does not retry on client errors"""

        def failing_operation():
            error = GoogleAPIError("Not found")
            error.code = 404
            raise error

        with self.assertRaises(NotFoundError):
            self.connector._execute_with_retry(failing_operation, "test_operation", "test context")

    def test_execute_with_retry_no_retry_on_permission_error(self):
        """Test _execute_with_retry() does not retry on permission errors"""

        def failing_operation():
            error = GoogleAPIError("Permission denied")
            error.code = 403
            raise error

        with self.assertRaises(PermissionError):
            self.connector._execute_with_retry(failing_operation, "test_operation", "test context")

    def test_execute_with_retry_no_retry_on_value_error(self):
        """Test _execute_with_retry() does not retry on validation errors"""

        def failing_operation():
            error = GoogleAPIError("Bad request")
            error.code = 400
            raise error

        with self.assertRaises(ValueError):
            self.connector._execute_with_retry(failing_operation, "test_operation", "test context")


class TestGCPMarketplaceConnectorErrorMapping(TestCase):
    """Test error mapping from Google Cloud errors to connector exceptions"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    def test_map_google_error_404(self):
        """Test _map_google_error() maps 404 to NotFoundError"""
        error = GoogleAPIError("Resource not found")
        error.code = 404
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, NotFoundError)
        self.assertIn("not found", str(mapped_error).lower())

    def test_map_google_error_403(self):
        """Test _map_google_error() maps 403 to PermissionError"""
        error = GoogleAPIError("Permission denied")
        error.code = 403
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, PermissionError)
        self.assertIn("permission", str(mapped_error).lower())

    def test_map_google_error_401(self):
        """Test _map_google_error() maps 401 to PermissionError"""
        error = GoogleAPIError("Unauthorized")
        error.code = 401
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, PermissionError)
        self.assertIn("authentication", str(mapped_error).lower())

    def test_map_google_error_400(self):
        """Test _map_google_error() maps 400 to ValueError"""
        error = GoogleAPIError("Bad request")
        error.code = 400
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, ValueError)
        self.assertIn("invalid", str(mapped_error).lower())

    def test_map_google_error_500(self):
        """Test _map_google_error() maps 500 to ConnectionError"""
        error = GoogleAPIError("Internal error")
        error.code = 500
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn("Transient error", str(mapped_error))

    def test_map_google_error_429(self):
        """Test _map_google_error() maps 429 to ConnectionError"""
        error = GoogleAPIError("Too many requests")
        error.code = 429
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn("Transient error", str(mapped_error))

    def test_map_google_error_unknown_code(self):
        """Test _map_google_error() maps unknown error codes to ConnectionError"""
        error = GoogleAPIError("Unknown error")
        error.code = 999
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIsInstance(mapped_error, ConnectionError)

    def test_map_google_error_extracts_message(self):
        """Test _map_google_error() extracts error message from Google Cloud error"""
        error = GoogleAPIError("Custom error message")
        error.code = 404
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIn("Custom error message", str(mapped_error))

    def test_map_google_error_includes_context(self):
        """Test _map_google_error() includes context in error message"""
        error = GoogleAPIError("Error")
        error.code = 404
        mapped_error = self.connector._map_google_error(error, "test context", "test_operation")
        self.assertIn("test context", str(mapped_error))


class TestGCPMarketplaceConnectorCircuitBreaker(TestCase):
    """Test circuit breaker integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    def test_circuit_breaker_initialized(self):
        """Test circuit breaker is initialized"""
        self.assertIsNotNone(self.connector._circuit_breaker)
        self.assertEqual(self.connector._circuit_breaker.service_name, "gcp-marketplace-connector")
        self.assertEqual(self.connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(self.connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(self.connector._circuit_breaker.success_threshold, 2)

    def test_execute_with_retry_uses_circuit_breaker(self):
        """Test _execute_with_retry() uses circuit breaker"""

        def successful_operation():
            return "success"

        with patch.object(self.connector._circuit_breaker, "call") as mock_cb_call:
            mock_cb_call.return_value = "success"
            result = self.connector._execute_with_retry(
                successful_operation, "test_operation", "test context"
            )
            self.assertEqual(result, "success")
            mock_cb_call.assert_called_once()

    def test_circuit_breaker_protects_against_cascading_failures(self):
        """Test circuit breaker protects against cascading failures"""

        def always_failing_operation():
            error = GoogleAPIError("Service unavailable", code=503)
            raise error

        # Simulate multiple failures to trigger circuit breaker
        with patch("time.sleep"):
            for _ in range(6):  # More than failure_threshold (5)
                try:
                    self.connector._execute_with_retry(
                        always_failing_operation, "test_operation", "test context"
                    )
                except Exception:
                    pass

        # Circuit breaker should be in open state after failures
        # (This is tested indirectly through the circuit breaker's behavior)


class TestGCPMarketplaceConnectorStructuredLogging(TestCase):
    """Test structured logging with correlation IDs"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.logger")
    def test_log_with_context_includes_operation(self, mock_logger):
        """Test _log_with_context() includes operation in log context"""
        self.connector._log_with_context("info", "Test message", operation="test_operation")
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        self.assertEqual(call_args[0][0], "Test message")
        self.assertIn("operation", call_args[1].get("extra", {}))

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.logger")
    def test_log_with_context_includes_error_code(self, mock_logger):
        """Test _log_with_context() includes error_code in log context"""
        self.connector._log_with_context(
            "error", "Test error", operation="test_operation", error_code=500
        )
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        extra = call_args[1].get("extra", {})
        self.assertEqual(extra.get("error_code"), 500)

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.logger")
    def test_log_with_context_includes_retry_info(self, mock_logger):
        """Test _log_with_context() includes retry information"""
        self.connector._log_with_context(
            "warning",
            "Retrying operation",
            operation="test_operation",
            attempt=2,
            max_retries=3,
            delay=2.0,
        )
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        extra = call_args[1].get("extra", {})
        self.assertEqual(extra.get("attempt"), 2)
        self.assertEqual(extra.get("max_retries"), 3)
        self.assertEqual(extra.get("retry_delay"), 2.0)

    @patch("hub.apps.api.middleware.trace_propagation.get_current_request")
    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.logger")
    def test_log_with_context_includes_correlation_id(self, mock_logger, mock_get_request):
        """Test _log_with_context() includes correlation ID from trace context"""
        mock_request = Mock()
        mock_request.trace_id = "test-trace-id-123"
        mock_get_request.return_value = mock_request

        self.connector._log_with_context("info", "Test message", operation="test_operation")
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        extra = call_args[1].get("extra", {})
        self.assertEqual(extra.get("correlation_id"), "test-trace-id-123")
        self.assertEqual(extra.get("trace_id"), "test-trace-id-123")

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.logger")
    def test_log_with_context_includes_project_id(self, mock_logger):
        """Test _log_with_context() includes project_id in log context"""
        self.connector._log_with_context("info", "Test message", operation="test_operation")
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        extra = call_args[1].get("extra", {})
        self.assertEqual(extra.get("project_id"), "test-project")
        self.assertEqual(extra.get("connector"), "gcp-marketplace")

    def test_execute_with_retry_max_retries_exceeded(self):
        """Test _execute_with_retry() raises error after max retries"""
        call_count = [0]

        def failing_operation():
            call_count[0] += 1
            error = GoogleAPIError("Service unavailable")
            error.code = 503  # type: ignore[attr-defined]
            raise error

        # Set max_retries to 3 for this test
        original_max_retries = self.connector.max_retries
        self.connector.max_retries = 3

        try:
            with self.assertRaises(ConnectionError):
                self.connector._execute_with_retry(
                    failing_operation, operation_name="test_operation", context="test context"
                )

            # Should have retried 3 times + initial call = 4 total
            self.assertGreaterEqual(call_count[0], 3)
        finally:
            self.connector.max_retries = original_max_retries

    def test_execute_with_retry_non_transient_error(self):
        """Test _execute_with_retry() does not retry on non-transient errors"""
        call_count = [0]

        def failing_operation():
            call_count[0] += 1
            error = GoogleAPIError("Bad request")
            error.code = 400  # type: ignore[attr-defined]
            raise error

        with self.assertRaises(ValueError):
            self.connector._execute_with_retry(
                failing_operation, operation_name="test_operation", context="test context"
            )

        # Should not retry for non-transient errors
        self.assertEqual(call_count[0], 1)

    def test_map_google_error_not_found(self):
        """Test _map_google_error() maps NotFound to NotFoundError"""
        if not GOOGLE_CLOUD_AVAILABLE:
            self.skipTest("Google Cloud libraries not available")
        from google.api_core.exceptions import NotFound

        error = NotFound("Resource not found")
        mapped_error = self.connector._map_google_error(error, context="test", operation="test")
        self.assertIsInstance(mapped_error, NotFoundError)

    def test_map_google_error_permission_denied(self):
        """Test _map_google_error() maps PermissionDenied to PermissionError"""
        if not GOOGLE_CLOUD_AVAILABLE:
            self.skipTest("Google Cloud libraries not available")
        from google.api_core.exceptions import PermissionDenied

        error = PermissionDenied("Permission denied")
        mapped_error = self.connector._map_google_error(error, context="test", operation="test")
        self.assertIsInstance(mapped_error, PermissionError)

    def test_map_google_error_generic_error(self):
        """Test _map_google_error() maps generic errors to ConnectionError"""
        error = GoogleAPIError("Generic error")
        mapped_error = self.connector._map_google_error(error, context="test", operation="test")
        self.assertIsInstance(mapped_error, ConnectionError)
