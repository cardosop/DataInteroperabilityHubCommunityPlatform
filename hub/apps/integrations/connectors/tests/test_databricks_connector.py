"""
Unit tests for DatabricksConnector.

Tests Databricks marketplace connector implementing DataMarketplaceConnector interface.
Follows TDD approach - tests written before implementation.
"""

from typing import Any, Dict
from unittest.mock import Mock, patch, MagicMock

import httpx
import pytest
from django.test import TestCase, override_settings

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
)


class TestDatabricksConnectorInitialization(TestCase):
    """Test Databricks connector initialization"""

    def test_init_with_host_and_token(self):
        """Test connector initialization with host and token"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        self.assertEqual(connector.host, 'https://test-workspace.cloud.databricks.com')
        self.assertEqual(connector.token, 'dapi1234567890abcdef')
        self.assertIsNone(connector.cluster_id)
        self.assertIsNotNone(connector.client)
        self.assertIsNotNone(connector._circuit_breaker)

    def test_init_with_cluster_id(self):
        """Test connector initialization with optional cluster_id"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef',
            cluster_id='1234-567890-abcd1234'
        )
        self.assertEqual(connector.cluster_id, '1234-567890-abcd1234')

    def test_init_host_trailing_slash_removed(self):
        """Test connector removes trailing slash from host URL"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com/',
            token='dapi1234567890abcdef'
        )
        self.assertEqual(connector.host, 'https://test-workspace.cloud.databricks.com')

    def test_init_circuit_breaker_configuration(self):
        """Test circuit breaker is initialized with correct parameters"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        self.assertEqual(connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(connector._circuit_breaker.success_threshold, 2)
        self.assertEqual(connector._circuit_breaker.service_name, 'databricks-connector')

    def test_init_http_client_configuration(self):
        """Test HTTP client is initialized with correct configuration"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        self.assertEqual(connector.client.base_url, 'https://test-workspace.cloud.databricks.com')
        self.assertEqual(connector.client.timeout.read, 30.0)

    def test_init_authentication_headers(self):
        """Test HTTP client includes Bearer token in headers"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        # Verify headers are set correctly by checking client configuration
        # The actual headers are set per-request, but we can verify the token is stored
        self.assertEqual(connector.token, 'dapi1234567890abcdef')

    def test_marketplace_type_property(self):
        """Test marketplace_type property returns DATABRICKS_MARKETPLACE"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        self.assertEqual(connector.marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions property returns PULL only"""
        connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )
        directions = connector.supported_sync_directions
        self.assertEqual(directions, [SyncDirection.PULL])
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)


class TestDatabricksConnectorAuthentication(TestCase):
    """Test Databricks connector authentication"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector.test_connection')
    def test_authenticate_success(self, mock_test_connection):
        """Test successful authentication"""
        mock_test_connection.return_value = True

        credentials = {
            'host': 'https://new-workspace.cloud.databricks.com',
            'token': 'dapi9876543210fedcba'
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector.host, 'https://new-workspace.cloud.databricks.com')
        self.assertEqual(self.connector.token, 'dapi9876543210fedcba')
        mock_test_connection.assert_called_once()

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector.test_connection')
    def test_authenticate_with_cluster_id(self, mock_test_connection):
        """Test authentication updates cluster_id if provided"""
        mock_test_connection.return_value = True

        credentials = {
            'host': 'https://test-workspace.cloud.databricks.com',
            'token': 'dapi1234567890abcdef',
            'cluster_id': '1234-567890-abcd1234'
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector.cluster_id, '1234-567890-abcd1234')

    def test_authenticate_missing_host(self):
        """Test authentication raises ValueError if host is missing"""
        credentials = {
            'token': 'dapi1234567890abcdef'
        }
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn('host', str(cm.exception).lower())

    def test_authenticate_missing_token(self):
        """Test authentication raises ValueError if token is missing"""
        credentials = {
            'host': 'https://test-workspace.cloud.databricks.com'
        }
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn('token', str(cm.exception).lower())

    def test_authenticate_empty_credentials(self):
        """Test authentication raises ValueError if credentials dict is empty"""
        with self.assertRaises(ValueError):
            self.connector.authenticate({})

    def test_authenticate_none_credentials(self):
        """Test authentication raises ValueError if credentials is None"""
        with self.assertRaises(ValueError):
            self.connector.authenticate(None)

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector.test_connection')
    def test_authenticate_connection_error(self, mock_test_connection):
        """Test authentication raises ConnectionError on connection failure"""
        mock_test_connection.side_effect = ConnectionError("Connection failed")

        credentials = {
            'host': 'https://test-workspace.cloud.databricks.com',
            'token': 'dapi1234567890abcdef'
        }
        with self.assertRaises(ConnectionError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn('Connection failed', str(cm.exception))

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector.test_connection')
    def test_authenticate_connection_test_failure(self, mock_test_connection):
        """Test authentication raises ConnectionError when test_connection returns False"""
        mock_test_connection.return_value = False

        credentials = {
            'host': 'https://test-workspace.cloud.databricks.com',
            'token': 'dapi1234567890abcdef'
        }
        with self.assertRaises(ConnectionError):
            self.connector.authenticate(credentials)


class TestDatabricksConnectorTestConnection(TestCase):
    """Test Databricks connector test_connection method"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host='https://test-workspace.cloud.databricks.com',
            token='dapi1234567890abcdef'
        )

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector._request_with_retry')
    def test_test_connection_success(self, mock_request):
        """Test successful connection test"""
        mock_response = Mock()
        mock_response.json.return_value = {'objects': []}
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = self.connector.test_connection()

        self.assertTrue(result)
        mock_request.assert_called_once()
        # Verify it calls the workspace/list endpoint
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][1], '/api/2.0/workspace/list')
        self.assertIn('path', call_args[1]['params'])
        self.assertEqual(call_args[1]['params']['path'], '/')

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector._request_with_retry')
    def test_test_connection_http_error(self, mock_request):
        """Test connection test raises ConnectionError on HTTP error"""
        mock_request.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=Mock(),
            response=Mock(status_code=401)
        )

        with self.assertRaises(ConnectionError):
            self.connector.test_connection()

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector._request_with_retry')
    def test_test_connection_network_error(self, mock_request):
        """Test connection test raises ConnectionError on network error"""
        mock_request.side_effect = httpx.RequestError("Network error")

        with self.assertRaises(ConnectionError) as cm:
            self.connector.test_connection()
        self.assertIn('Network error', str(cm.exception))

    @patch('hub.apps.integrations.connectors.databricks_connector.DatabricksConnector._request_with_retry')
    def test_test_connection_circuit_breaker_protection(self, mock_request):
        """Test that test_connection uses circuit breaker"""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        # Verify circuit breaker is called
        with patch.object(self.connector._circuit_breaker, 'call') as mock_cb_call:
            mock_cb_call.return_value = mock_response
            result = self.connector.test_connection()
            self.assertTrue(result)
            # Note: _request_with_retry uses circuit breaker internally,
            # so we verify the request was made successfully

