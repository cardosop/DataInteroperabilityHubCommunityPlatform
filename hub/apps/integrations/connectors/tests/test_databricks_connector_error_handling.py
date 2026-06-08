"""
Unit tests for DatabricksConnector error handling, retry logic, and circuit breaker.

Tests error handling, retry logic with exponential backoff, circuit breaker protection,
and distributed tracing for Databricks connector.
"""

from typing import Any, Dict
from unittest.mock import Mock, patch, MagicMock

import httpx
import pytest
import time
from django.test import TestCase, override_settings

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.core.services.base import NotFoundError


class TestDatabricksConnectorErrorHandling(TestCase):
    """Test error handling and exception mapping"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    def test_map_databricks_error_404_to_not_found_error(self):
        """Test that 404 errors are mapped to NotFoundError"""
        error_response = Mock()
        error_response.status_code = 404
        error_response.json.return_value = {
            'error_code': 'RESOURCE_DOES_NOT_EXIST',
            'message': 'Share not found'
        }
        error_response.text = '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Share not found"}'

        error = httpx.HTTPStatusError('Not Found', request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context='test: ')

        self.assertIsInstance(mapped_error, NotFoundError)
        self.assertIn('Share not found', str(mapped_error))

    def test_map_databricks_error_403_to_permission_error(self):
        """Test that 403 errors are mapped to PermissionError"""
        error_response = Mock()
        error_response.status_code = 403
        error_response.json.return_value = {
            'error_code': 'PERMISSION_DENIED',
            'message': 'Access denied'
        }
        error_response.text = '{"error_code": "PERMISSION_DENIED", "message": "Access denied"}'

        error = httpx.HTTPStatusError('Forbidden', request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context='test: ')

        self.assertIsInstance(mapped_error, PermissionError)
        self.assertIn('Access denied', str(mapped_error))

    def test_map_databricks_error_400_to_value_error(self):
        """Test that 400 errors are mapped to ValueError"""
        error_response = Mock()
        error_response.status_code = 400
        error_response.json.return_value = {
            'error_code': 'INVALID_PARAMETER_VALUE',
            'message': 'Invalid parameter'
        }
        error_response.text = '{"error_code": "INVALID_PARAMETER_VALUE", "message": "Invalid parameter"}'

        error = httpx.HTTPStatusError('Bad Request', request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context='test: ')

        self.assertIsInstance(mapped_error, ValueError)
        self.assertIn('Invalid parameter', str(mapped_error))

    def test_map_databricks_error_429_to_connection_error(self):
        """Test that 429 errors are mapped to ConnectionError (transient)"""
        error_response = Mock()
        error_response.status_code = 429
        error_response.json.return_value = {
            'error_code': 'TOO_MANY_REQUESTS',
            'message': 'Rate limit exceeded'
        }
        error_response.text = '{"error_code": "TOO_MANY_REQUESTS", "message": "Rate limit exceeded"}'

        error = httpx.HTTPStatusError('Too Many Requests', request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context='test: ')

        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn('Rate limit exceeded', str(mapped_error))

    def test_map_databricks_error_500_to_connection_error(self):
        """Test that 500 errors are mapped to ConnectionError (transient)"""
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {
            'error_code': 'INTERNAL_SERVER_ERROR',
            'message': 'Internal server error'
        }
        error_response.text = '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal server error"}'

        error = httpx.HTTPStatusError('Internal Server Error', request=Mock(), response=error_response)
        mapped_error = self.connector._map_databricks_error(error, context='test: ')

        self.assertIsInstance(mapped_error, ConnectionError)
        self.assertIn('Internal server error', str(mapped_error))

    def test_extract_error_message_from_json_response(self):
        """Test extracting error message from JSON response"""
        response = Mock()
        response.json.return_value = {
            'error_code': 'RESOURCE_DOES_NOT_EXIST',
            'message': 'Share not found'
        }
        response.text = '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Share not found"}'
        response.status_code = 404

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, 'Share not found')

    def test_extract_error_message_from_nested_error(self):
        """Test extracting error message from nested error structure"""
        response = Mock()
        response.json.return_value = {
            'error': {
                'message': 'Nested error message'
            }
        }
        response.text = '{"error": {"message": "Nested error message"}}'
        response.status_code = 400

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, 'Nested error message')

    def test_extract_error_message_fallback_to_text(self):
        """Test fallback to response text if JSON parsing fails"""
        response = Mock()
        response.json.side_effect = ValueError('Invalid JSON')
        response.text = 'Plain text error message'
        response.status_code = 500

        error_message = self.connector._extract_error_message(response)
        self.assertEqual(error_message, 'Plain text error message')

    def test_extract_error_message_fallback_to_status_code(self):
        """Test fallback to status code if text is empty"""
        response = Mock()
        response.json.side_effect = ValueError('Invalid JSON')
        response.text = ''
        response.status_code = 500

        error_message = self.connector._extract_error_message(response)
        self.assertIn('500', error_message)

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
    """Test retry logic with exponential backoff"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    @patch('hub.apps.integrations.connectors.databricks_connector.time.sleep')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_retry_on_429_error(self, mock_circuit_breaker_class, mock_sleep):
        """Test that 429 errors are retried with exponential backoff"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock client to fail twice then succeed
        error_response = Mock()
        error_response.status_code = 429
        error_response.json.return_value = {'error_code': 'TOO_MANY_REQUESTS', 'message': 'Rate limit exceeded'}
        error_response.text = '{"error_code": "TOO_MANY_REQUESTS", "message": "Rate limit exceeded"}'
        error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError('Too Many Requests', request=Mock(), response=error_response))

        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        connector.client.request = Mock(side_effect=[
            error_response,
            error_response,
            success_response
        ])

        # Execute request
        response = connector._request_with_retry('GET', '/api/2.0/test')

        # Verify retries occurred
        self.assertEqual(connector.client.request.call_count, 3)
        # Verify exponential backoff delays
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1.0)  # backoff_factor * (2 ** 0) = 1
        mock_sleep.assert_any_call(2.0)  # backoff_factor * (2 ** 1) = 2

    @patch('hub.apps.integrations.connectors.databricks_connector.time.sleep')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_retry_on_500_error(self, mock_circuit_breaker_class, mock_sleep):
        """Test that 500 errors are retried with exponential backoff"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock client to fail twice then succeed
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {'error_code': 'INTERNAL_SERVER_ERROR', 'message': 'Internal error'}
        error_response.text = '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal error"}'
        error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError('Internal Server Error', request=Mock(), response=error_response))

        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        connector.client.request = Mock(side_effect=[
            error_response,
            error_response,
            success_response
        ])

        # Execute request
        response = connector._request_with_retry('GET', '/api/2.0/test')

        # Verify retries occurred
        self.assertEqual(connector.client.request.call_count, 3)
        # Verify exponential backoff delays
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_no_retry_on_404_error(self, mock_circuit_breaker_class):
        """Test that 404 errors are NOT retried"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock client to return 404
        error_response = Mock()
        error_response.status_code = 404
        error_response.json.return_value = {'error_code': 'RESOURCE_DOES_NOT_EXIST', 'message': 'Not found'}
        error_response.text = '{"error_code": "RESOURCE_DOES_NOT_EXIST", "message": "Not found"}'
        error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError('Not Found', request=Mock(), response=error_response))

        connector.client.request = Mock(return_value=error_response)

        # Execute request and expect NotFoundError
        with self.assertRaises(NotFoundError):
            connector._request_with_retry('GET', '/api/2.0/test')

        # Verify no retries occurred
        self.assertEqual(connector.client.request.call_count, 1)

    @patch('hub.apps.integrations.connectors.databricks_connector.time.sleep')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_max_retries_exceeded(self, mock_circuit_breaker_class, mock_sleep):
        """Test that max retries exceeded raises ConnectionError"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock client to always return 500
        error_response = Mock()
        error_response.status_code = 500
        error_response.json.return_value = {'error_code': 'INTERNAL_SERVER_ERROR', 'message': 'Internal error'}
        error_response.text = '{"error_code": "INTERNAL_SERVER_ERROR", "message": "Internal error"}'
        error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError('Internal Server Error', request=Mock(), response=error_response))

        connector.client.request = Mock(return_value=error_response)

        # Execute request and expect ConnectionError (mapped error after max retries)
        with self.assertRaises(ConnectionError) as context:
            connector._request_with_retry('GET', '/api/2.0/test')

        # Verify max retries were attempted (max_retries + 1 = 3 attempts)
        self.assertEqual(connector.client.request.call_count, 3)
        # After max retries, the mapped error is raised (not generic "Max retries exceeded")
        self.assertIn('Transient Databricks error', str(context.exception))
        self.assertIn('500', str(context.exception))

    @patch('hub.apps.integrations.connectors.databricks_connector.time.sleep')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_retry_on_network_error(self, mock_circuit_breaker_class, mock_sleep):
        """Test that network errors are retried"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock client to raise network error twice then succeed
        network_error = httpx.RequestError('Network error', request=Mock())
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()

        connector.client.request = Mock(side_effect=[
            network_error,
            network_error,
            success_response
        ])

        # Execute request
        response = connector._request_with_retry('GET', '/api/2.0/test')

        # Verify retries occurred
        self.assertEqual(connector.client.request.call_count, 3)
        # Verify exponential backoff delays
        self.assertEqual(mock_sleep.call_count, 2)


class TestDatabricksConnectorCircuitBreaker(TestCase):
    """Test circuit breaker integration"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_circuit_breaker_open_state(self, mock_circuit_breaker_class):
        """Test that circuit breaker open state is handled gracefully"""
        # Setup circuit breaker mock to raise exception when open
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=Exception('Circuit breaker is open'))
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Execute request and expect ConnectionError
        with self.assertRaises(ConnectionError) as context:
            connector._request_with_retry('GET', '/api/2.0/test')

        self.assertIn('Circuit breaker is open', str(context.exception))

    def test_circuit_breaker_configuration(self):
        """Test that circuit breaker is configured correctly"""
        self.assertEqual(self.connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(self.connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(self.connector._circuit_breaker.success_threshold, 2)
        self.assertEqual(self.connector._circuit_breaker.service_name, 'databricks-connector')


class TestDatabricksConnectorDistributedTracing(TestCase):
    """Test distributed tracing support"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    @patch('hub.apps.api.middleware.trace_propagation.get_trace_headers')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_trace_headers_added_to_request(self, mock_circuit_breaker_class, mock_get_trace_headers):
        """Test that trace headers are added to requests"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Setup trace headers mock
        trace_headers = {
            'X-Trace-Id': 'trace-123',
            'X-Span-Id': 'span-456'
        }
        mock_get_trace_headers.return_value = trace_headers

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock successful response
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()
        connector.client.request = Mock(return_value=success_response)

        # Execute request
        connector._request_with_retry('GET', '/api/2.0/test')

        # Verify trace headers were added
        call_args = connector.client.request.call_args
        headers = call_args[1].get('headers', {})
        self.assertIn('X-Trace-Id', headers)
        self.assertEqual(headers['X-Trace-Id'], 'trace-123')

    @patch('hub.apps.api.middleware.trace_propagation.get_trace_headers')
    @patch('hub.apps.integrations.connectors.databricks_connector.CircuitBreaker')
    def test_no_trace_headers_when_not_available(self, mock_circuit_breaker_class, mock_get_trace_headers):
        """Test that request works when trace headers are not available"""
        # Setup circuit breaker mock
        mock_circuit_breaker = Mock()
        mock_circuit_breaker.call = Mock(side_effect=lambda func: func())
        mock_circuit_breaker_class.return_value = mock_circuit_breaker

        # Setup trace headers mock to return None
        mock_get_trace_headers.return_value = None

        # Create connector with mocked circuit breaker
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        connector._circuit_breaker = mock_circuit_breaker

        # Mock successful response
        success_response = Mock()
        success_response.status_code = 200
        success_response.raise_for_status = Mock()
        connector.client.request = Mock(return_value=success_response)

        # Execute request (should not raise exception)
        connector._request_with_retry('GET', '/api/2.0/test')

        # Verify request was made
        self.assertEqual(connector.client.request.call_count, 1)

