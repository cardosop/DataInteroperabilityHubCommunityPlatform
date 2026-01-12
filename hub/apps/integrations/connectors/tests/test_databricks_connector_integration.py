"""
Integration tests for DatabricksConnector with real Databricks API.

Tests use real Databricks API endpoints - no mocks or stubs.
Uses Bearer token authentication.
"""
import os
import pytest
from django.test import TestCase

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.base import MarketplaceType, SyncDirection
from hub.apps.core.services.base import NotFoundError


@pytest.mark.integration
class TestDatabricksConnectorIntegration(TestCase):
    """
    Integration tests for DatabricksConnector with real Databricks API.

    Tests use real Databricks API endpoints - no mocks or stubs.
    Requires DATABRICKS_HOST and DATABRICKS_TOKEN environment variables.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real Databricks connector."""
        super().setUpClass()

        # Get credentials from environment
        cls.host = os.getenv('DATABRICKS_HOST')
        cls.token = os.getenv('DATABRICKS_TOKEN')
        cls.cluster_id = os.getenv('DATABRICKS_CLUSTER_ID')  # Optional

        if not cls.host or not cls.token:
            pytest.skip("DATABRICKS_HOST and DATABRICKS_TOKEN not set - skipping integration tests")

        # Create connector
        assert cls.host is not None
        assert cls.token is not None
        cls.connector = DatabricksConnector(
            host=cls.host,
            token=cls.token,
            cluster_id=cls.cluster_id
        )

    def setUp(self):
        """Set up test fixtures"""
        if not self.host or not self.token:
            self.skipTest("DATABRICKS_HOST and DATABRICKS_TOKEN not set - skipping integration tests")

    def test_connector_initialization(self):
        """Test that connector initializes correctly."""
        assert self.connector is not None
        assert self.host is not None
        assert self.token is not None
        assert self.connector.host == self.host.rstrip('/')
        assert self.connector.token == self.token
        assert self.connector.client is not None
        assert self.connector._circuit_breaker is not None

    def test_marketplace_type(self):
        """Test that marketplace type is DATABRICKS_MARKETPLACE."""
        assert self.connector.marketplace_type == MarketplaceType.DATABRICKS_MARKETPLACE

    def test_supported_sync_directions(self):
        """Test that connector supports only PULL (harvest-only)."""
        assert self.connector.supported_sync_directions == [SyncDirection.PULL]
        assert SyncDirection.PUSH not in self.connector.supported_sync_directions
        assert SyncDirection.BIDIRECTIONAL not in self.connector.supported_sync_directions

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker is configured correctly."""
        assert self.connector._circuit_breaker.failure_threshold == 5
        assert self.connector._circuit_breaker.timeout_seconds == 60
        assert self.connector._circuit_breaker.success_threshold == 2
        assert self.connector._circuit_breaker.service_name == 'databricks-connector'

    def test_authenticate(self):
        """Test authentication with real Databricks API."""
        try:
            credentials = {
                'host': self.host,
                'token': self.token
            }
            if self.cluster_id:
                credentials['cluster_id'] = self.cluster_id

            result = self.connector.authenticate(credentials)
            assert result is True
            assert self.connector._authenticated is True
        except ConnectionError as e:
            error_str = str(e).lower()
            if 'authentication failed' in error_str or 'unauthorized' in error_str or 'invalid token' in error_str:
                pytest.skip(f"Databricks authentication failed (token may be expired or invalid): {e}")
            pytest.fail(f"Authentication failed: {e}")
        except Exception as e:
            pytest.fail(f"Authentication failed: {e}")

    def test_test_connection(self):
        """Test connection to Databricks API."""
        try:
            result = self.connector.test_connection()
            assert result is True
            assert self.connector._authenticated is True
        except ConnectionError as e:
            error_str = str(e).lower()
            if 'authentication failed' in error_str or 'unauthorized' in error_str or 'invalid token' in error_str:
                pytest.skip(f"Databricks connection test failed (token may be expired or invalid): {e}")
            pytest.fail(f"Connection test failed: {e}")
        except Exception as e:
            pytest.fail(f"Connection test failed: {e}")

    def test_authenticate_with_updated_credentials(self):
        """Test authentication updates credentials correctly."""
        assert self.host is not None
        assert self.token is not None
        try:
            # Test with same credentials (should work)
            credentials = {
                'host': self.host,
                'token': self.token
            }
            result = self.connector.authenticate(credentials)
            assert result is True
            assert self.connector.host == self.host.rstrip('/')
            assert self.connector.token == self.token
        except ConnectionError as e:
            error_str = str(e).lower()
            if 'authentication failed' in error_str or 'unauthorized' in error_str:
                pytest.skip(f"Databricks authentication failed: {e}")
            pytest.fail(f"Authentication failed: {e}")

    def test_authenticate_with_cluster_id(self):
        """Test authentication with cluster_id if provided."""
        if not self.cluster_id:
            pytest.skip("DATABRICKS_CLUSTER_ID not set - skipping cluster_id test")

        try:
            credentials = {
                'host': self.host,
                'token': self.token,
                'cluster_id': self.cluster_id
            }
            result = self.connector.authenticate(credentials)
            assert result is True
            assert self.connector.cluster_id == self.cluster_id
        except ConnectionError as e:
            error_str = str(e).lower()
            if 'authentication failed' in error_str or 'unauthorized' in error_str:
                pytest.skip(f"Databricks authentication failed: {e}")
            pytest.fail(f"Authentication failed: {e}")

    def test_http_client_configuration(self):
        """Test HTTP client is configured correctly."""
        assert self.host is not None
        assert self.token is not None
        assert self.connector.client.base_url == self.host.rstrip('/')
        assert self.connector.client.timeout.read == 30.0
        # Verify headers include Bearer token
        headers = self.connector._get_default_headers()
        assert 'Authorization' in headers
        assert headers['Authorization'] == f'Bearer {self.token}'
        assert headers['Content-Type'] == 'application/json'
        assert headers['Accept'] == 'application/json'

