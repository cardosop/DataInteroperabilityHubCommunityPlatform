"""
Unit tests for DatabricksConnector error handling, retry logic, and circuit breaker.

Tests error handling, retry logic with exponential backoff, circuit breaker protection,
and distributed tracing for Databricks connector.
"""

from unittest.mock import Mock, patch

import httpx
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


class TestDatabricksConnectorErrorHandling(TestCase):
    """Test error handling and exception mapping"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="dapi1234567890abcdef"
        )

    def test_map_databricks_error_404_to_not_found_error(self):
        """Test that 404 errors are mapped to NotFoundError"""
        error_response = Mock()
        error_response.status_code = 404
        error_response.json.return_value = {
            "error_code": "RESOURCE_DOES_NOT_EXIST",
            "message": "Share not found",
        }
        error_response.text = (
            '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Share not found"}'
        )

        error = httpx.HTTPStatusError("Not Found", request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context="test: ")

        self.assertIsInstance(mapped_error, NotFoundError)
        self.assertIn("Share not found", str(mapped_error))

    def test_map_databricks_error_403_to_permission_error(self):
        """Test that 403 errors are mapped to PermissionError"""
        error_response = Mock()
        error_response.status_code = 403
        error_response.json.return_value = {
            "error_code": "PERMISSION_DENIED",
            "message": "Access denied",
        }
        error_response.text = '{"error_code": "PERMISSION_DENIED", "message": "Access denied"}'

        error = httpx.HTTPStatusError("Forbidden", request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context="test: ")

        self.assertIsInstance(mapped_error, PermissionError)
        self.assertIn("Access denied", str(mapped_error))

    def test_map_databricks_error_400_to_value_error(self):
        """Test that 400 errors are mapped to ValueError"""
        error_response = Mock()
        error_response.status_code = 400
        error_response.json.return_value = {
            "error_code": "INVALID_PARAMETER_VALUE",
            "message": "Invalid parameter",
        }
        error_response.text = (
            '{"error_code": "INVALID_PARAMETER_VALUE", "message": "Invalid parameter"}'
        )

        error = httpx.HTTPStatusError("Bad Request", request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context="test: ")

        self.assertIsInstance(mapped_error, ValueError)
        self.assertIn("Invalid parameter", str(mapped_error))

    def test_map_databricks_error_429_to_connection_error(self):
        """Test that 429 errors are mapped to ConnectionError (transient)"""
        error_response = Mock()
        error_response.status_code = 429
        error_response.json.return_value = {
            "error_code": "TOO_MANY_REQUESTS",
            "message": "Rate limit exceeded",
        }
        error_response.text = (
            '{"error_code": "TOO_MANY_REQUESTS", "message": "Rate limit exceeded"}'
        )

        error = httpx.HTTPStatusError("Too Many Requests", request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context="test: ")

        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn("Rate limit exceeded", str(mapped_error))

    def test_map_databricks_error_500_to_connection_error(self):
        """Test that 500 errors are mapped to ConnectionError (transient)"""
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error",
        }
        error_response.text = (
            '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal server error"}'
        )

        error = httpx.HTTPStatusError(
            "Internal Server Error", request=Mock(), response=error_response
        )
        mapped_error = self.connector._map_databricks_error(error, context="test: ")

        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn("Internal server error", str(mapped_error))

    def test_extract_error_message_from_json_response(self):
        """Test extracting error message from JSON response"""
        response = Mock()
        response.json.return_value = {
            "error_code": "RESOURCE_DOES_NOT_EXIST",
            "message": "Share not found",
        }
        response.text = '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Share not found"}'
        response.status_code = 404

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, "Share not found")

    def test_extract_error_message_from_nested_error(self):
        """Test extracting error message from nested error structure"""
        response = Mock()
        response.json.return_value = {"error": {"message": "Nested error message"}}
        response.text = '{"error": {"message": "Nested error message"}}'
        response.status_code = 400

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, "Nested error message")

    def test_extract_error_message_fallback_to_text(self):
        """Test fallback to response text if JSON parsing fails"""
        response = Mock()
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "Plain text error message"
        response.status_code = 500

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, "Plain text error message")

    def test_extract_error_message_fallback_to_status_code(self):
        """Test fallback to status code if text is empty"""
        response = Mock()
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = ""
        response.status_code = 500

        error_message = self.connector._extract_error_message(response)
        self.assertIn("500", error_message)

    def test_is_transient_error_429(self):
        """Test that 429 is identified as transient error"""
        self.assertTrue(self.connector._is_transient_error(429))

    def test_is_transient_error_500(self):
        """Test that 500 is identified as transient error"""
        self.assertTrue(self.connector._is_transient_error(500))

    def test_is_transient_error_502(self):
        """Test that 502 is identified as transient error"""
        self.assertTrue(self.connector._is_transient_error(502))

    def test_is_transient_error_503(self):
        """Test that 503 is identified as transient error"""
        self.assertTrue(self.connector._is_transient_error(503))

    def test_is_transient_error_504(self):
        """Test that 504 is identified as transient error"""
        self.assertTrue(self.connector._is_transient_error(504))

    def test_is_transient_error_400(self):
        """Test that 400 is NOT identified as transient error"""
        self.assertFalse(self.connector._is_transient_error(400))

    def test_is_transient_error_404(self):
        """Test that 404 is NOT identified as transient error"""
        self.assertFalse(self.connector._is_transient_error(404))

    def test_is_transient_error_403(self):
        """Test that 403 is NOT identified as transient error"""
        self.assertFalse(self.connector._is_transient_error(403))


class TestDatabricksConnectorRetryLogic(TestCase):
    """Test retry logic with exponential backoff.

    Uses a **real** ``CircuitBreaker`` instance (no Redis — in-memory
    state) so that failure counting and state transitions are actually
    exercised, not bypassed by a mock.
    """

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="dapi1234567890abcdef"
        )

    @patch("hub.apps.integrations.connectors.databricks_connector.time.sleep")
    def test_retry_on_429_error(self, mock_sleep):
        """Test that 429 errors are retried with exponential backoff"""
        # Mock client.request to fail twice with 429 then succeed
        error_response = Mock()
        error_response.status_code = 429
        error_response.json.return_value = {
            "error_code": "TOO_MANY_REQUESTS",
            "message": "Rate limit exceeded",
        }
        error_response.text = (
            '{"error_code": "TOO_MANY_REQUESTS", "message": "Rate limit exceeded"}'
        )
        error_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests", request=Mock(), response=error_response
            )
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        self.connector.client.request = Mock(
            side_effect=[error_response, error_response, success_response]
        )

        # Execute request — uses the real CircuitBreaker from setUp
        self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify retries occurred
        self.assertEqual(self.connector.client.request.call_count, 3)
        # Verify exponential backoff delays
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1.0)  # backoff_factor * (2 ** 0) = 1
        mock_sleep.assert_any_call(2.0)  # backoff_factor * (2 ** 1) = 2
        # Real CB tracked failures and recovered
        self.assertEqual(self.connector._circuit_breaker._get_failure_count(), 0)

    @patch("hub.apps.integrations.connectors.databricks_connector.time.sleep")
    def test_retry_on_500_error(self, mock_sleep):
        """Test that 500 errors are retried with exponential backoff"""
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal error",
        }
        error_response.text = '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal error"}'
        error_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=Mock(), response=error_response
            )
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        self.connector.client.request = Mock(
            side_effect=[error_response, error_response, success_response]
        )

        # Execute request — real CircuitBreaker
        self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify retries occurred
        self.assertEqual(self.connector.client.request.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_no_retry_on_404_error(self):
        """Test that 404 errors are NOT retried"""
        error_response = Mock()
        error_response.status_code = 404
        error_response.json.return_value = {
            "error_code": "RESOURCE_DOES_NOT_EXIST",
            "message": "Not found",
        }
        error_response.text = '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Not found"}'
        error_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("Not Found", request=Mock(), response=error_response)
        )

        self.connector.client.request = Mock(return_value=error_response)

        # Execute request and expect NotFoundError
        with self.assertRaises(NotFoundError):
            self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify no retries occurred
        self.assertEqual(self.connector.client.request.call_count, 1)
        # Permanent (non-transient) failures should increment the CB counter
        self.assertEqual(self.connector._circuit_breaker._get_failure_count(), 1)

    @patch("hub.apps.integrations.connectors.databricks_connector.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        """Test that max retries exceeded raises ConnectionError"""
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal error",
        }
        error_response.text = '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal error"}'
        error_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=Mock(), response=error_response
            )
        )

        self.connector.client.request = Mock(return_value=error_response)

        # Execute request and expect ConnectionError (mapped error after max retries)
        with self.assertRaises(ConnectionError) as context:
            self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify max retries were attempted (max_retries + 1 = 3 attempts)
        self.assertEqual(self.connector.client.request.call_count, 3)
        self.assertIn("Transient Databricks error", str(context.exception))
        self.assertIn("500", str(context.exception))
        # The CB wraps the entire _request_with_retry call — 3 internal
        # HTTP retries count as 1 CB-level failure (the overall call failed).
        self.assertEqual(self.connector._circuit_breaker._get_failure_count(), 1)

    @patch("hub.apps.integrations.connectors.databricks_connector.time.sleep")
    def test_retry_on_network_error(self, mock_sleep):
        """Test that network errors are retried"""
        network_error = httpx.RequestError("Network error", request=Mock())
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        self.connector.client.request = Mock(
            side_effect=[network_error, network_error, success_response]
        )

        # Execute request — real CircuitBreaker tracks failures
        self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify retries occurred
        self.assertEqual(self.connector.client.request.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        # After 2 failures + 1 success, CB failure count should be 0
        self.assertEqual(self.connector._circuit_breaker._get_failure_count(), 0)


class TestDatabricksConnectorCircuitBreaker(TestCase):
    """Test circuit breaker integration"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="dapi1234567890abcdef"
        )

    def test_circuit_breaker_open_state(self):
        """Test that circuit breaker open state is handled gracefully.

        Uses a real ``CircuitBreaker`` and forces it into OPEN state
        by triggering enough failures to exceed the failure threshold.
        """
        from hub.apps.core.resilience.circuit_breaker import CircuitBreaker

        # Create a connector whose CB has a low threshold so we can
        # easily force it OPEN with a few failures.
        connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com",
            token="dapi1234567890abcdef",
        )
        # Replace the default CB with one that has a low threshold
        cb = CircuitBreaker(
            service_name="test-cb-open",
            failure_threshold=3,
            timeout_seconds=60,
            success_threshold=1,
        )
        connector._circuit_breaker = cb

        # Force the CB OPEN by triggering 3 failures
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal error",
        }
        error_response.text = (
            '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal error"}'
        )
        error_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=Mock(), response=error_response
            )
        )
        # First 3 requests fail → CB transitions to OPEN
        connector.client.request = Mock(return_value=error_response)
        for _ in range(3):
            with self.assertRaises(ConnectionError):
                connector._request_with_retry("GET", "/api/2.0/test")

        # Verify CB is now OPEN
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState

        self.assertEqual(cb._get_state(), CircuitBreakerState.OPEN)

        # Fourth request is immediately rejected by the open CB
        connector.client.request = Mock(
            return_value=Mock(status_code=200, raise_for_status=Mock())
        )
        with self.assertRaises(ConnectionError) as context:
            connector._request_with_retry("GET", "/api/2.0/test")
        self.assertIn("Circuit breaker is open", str(context.exception))
        # The HTTP client should NOT have been called — CB rejected it
        connector.client.request.assert_not_called()

    def test_circuit_breaker_configuration(self):
        """Test that circuit breaker is configured correctly"""
        self.assertEqual(self.connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(self.connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(self.connector._circuit_breaker.success_threshold, 2)
        self.assertEqual(self.connector._circuit_breaker.service_name, "databricks-connector")


class TestDatabricksConnectorDistributedTracing(TestCase):
    """Test distributed tracing support"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name

        reset_circuit_breaker_by_name("databricks-connector")
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com", token="dapi1234567890abcdef"
        )

    @patch("hub.apps.api.middleware.trace_propagation.get_trace_headers")
    def test_trace_headers_added_to_request(self, mock_get_trace_headers):
        """Test that trace headers are added to requests.

        Uses the real CircuitBreaker (in CLOSED state) so the request
        passes through and we can verify trace header propagation.
        """
        trace_headers = {"X-Trace-Id": "trace-123", "X-Span-Id": "span-456"}
        mock_get_trace_headers.return_value = trace_headers

        # Mock successful response; real CB from setUp handles pass-through
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()
        self.connector.client.request = Mock(return_value=success_response)

        # Execute request
        self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify trace headers were added
        call_args = self.connector.client.request.call_args
        headers = call_args[1].get("headers", {})
        self.assertIn("X-Trace-Id", headers)
        self.assertEqual(headers["X-Trace-Id"], "trace-123")

    @patch("hub.apps.api.middleware.trace_propagation.get_trace_headers")
    def test_no_trace_headers_when_not_available(self, mock_get_trace_headers):
        """Test that request works when trace headers are not available."""
        mock_get_trace_headers.return_value = None

        # Mock successful response; real CB from setUp provides pass-through
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()
        self.connector.client.request = Mock(return_value=success_response)

        # Execute request (should not raise exception)
        self.connector._request_with_retry("GET", "/api/2.0/test")

        # Verify request was made
        self.assertEqual(self.connector.client.request.call_count, 1)
