"""
Unit Tests for GCP Marketplace Connector

Tests the GCPMarketplaceConnector implementation including:
- Connector initialization
- Authentication (ADC and service account JSON)
- Connection testing
- Error handling
- Circuit breaker integration
"""

from unittest.mock import Mock, patch

# Optional Google Cloud imports - skip tests if not available
try:
    from google.api_core import exceptions as google_exceptions
    from google.auth.exceptions import GoogleAuthError

    # Use GoogleAPIError from google.api_core.exceptions
    GoogleAPIError = google_exceptions.GoogleAPIError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    google_exceptions = None
    GoogleAuthError = None
    GoogleAPIError = Exception  # Fallback
    GOOGLE_CLOUD_AVAILABLE = False

import pytest

pytestmark = pytest.mark.skipif(
    not GOOGLE_CLOUD_AVAILABLE, reason="Google Cloud libraries not installed"
)

from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.core.services.base import ConnectionError, NotFoundError, PermissionError
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
)
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector


class TestGCPMarketplaceConnectorInitialization(TestCase):
    """Test GCP Marketplace connector initialization"""

    def test_init_with_service_account_json(self):
        """Test connector initialization with service account JSON"""
        credentials_json = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=credentials_json
        )
        self.assertEqual(connector.project_id, "test-project")
        self.assertEqual(connector.credentials_json, credentials_json)
        self.assertEqual(connector.location, "US")
        self.assertFalse(connector.use_adc)
        self.assertEqual(connector.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)

    def test_init_with_adc(self):
        """Test connector initialization with Application Default Credentials"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)
        self.assertEqual(connector.project_id, "test-project")
        self.assertTrue(connector.use_adc)
        self.assertIsNone(connector.credentials_json)

    def test_init_with_custom_location(self):
        """Test connector initialization with custom location"""
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json={"type": "service_account"}, location="EU"
        )
        self.assertEqual(connector.location, "EU")

    def test_init_requires_authentication(self):
        """Test connector raises error if no authentication method provided"""
        with self.assertRaises(ValueError) as cm:
            GCPMarketplaceConnector(project_id="test-project")
        self.assertIn("use_adc", str(cm.exception).lower())
        self.assertIn("credentials_json", str(cm.exception).lower())

    def test_init_with_both_adc_and_credentials_json(self):
        """Test connector accepts both ADC flag and credentials_json (ADC takes precedence)"""
        credentials_json = {"type": "service_account"}
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=credentials_json, use_adc=True
        )
        self.assertTrue(connector.use_adc)
        # ADC takes precedence, but credentials_json is still stored

    def test_marketplace_type_property(self):
        """Test marketplace_type property returns correct value"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)
        self.assertEqual(connector.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions property returns PULL only"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)
        directions = connector.supported_sync_directions
        self.assertEqual(len(directions), 1)
        self.assertIn(SyncDirection.PULL, directions)
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker is properly initialized"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)
        self.assertIsNotNone(connector._circuit_breaker)
        self.assertEqual(connector._circuit_breaker.service_name, "gcp-marketplace-connector")
        self.assertEqual(connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(connector._circuit_breaker.success_threshold, 2)


class TestGCPMarketplaceConnectorCredentials(TestCase):
    """Test GCP Marketplace connector credential handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.credentials_json = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
        }

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.service_account.Credentials.from_service_account_info"
    )
    def test_get_credentials_with_service_account_json(self, mock_from_sa_info):
        """Test _get_credentials() with service account JSON"""
        mock_creds = Mock()
        mock_from_sa_info.return_value = mock_creds

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        credentials = connector._get_credentials()

        self.assertEqual(credentials, mock_creds)
        mock_from_sa_info.assert_called_once_with(self.credentials_json)

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.google_auth_default")
    def test_get_credentials_with_adc(self, mock_auth_default):
        """Test _get_credentials() with Application Default Credentials"""
        mock_creds = Mock()
        mock_project = "test-project"
        mock_auth_default.return_value = (mock_creds, mock_project)

        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        credentials = connector._get_credentials()

        self.assertEqual(credentials, mock_creds)
        mock_auth_default.assert_called_once()

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.google_auth_default")
    def test_get_credentials_with_adc_updates_project_id(self, mock_auth_default):
        """Test _get_credentials() with ADC updates project_id if not set"""
        mock_creds = Mock()
        mock_project = "adc-project"
        mock_auth_default.return_value = (mock_creds, mock_project)

        connector = GCPMarketplaceConnector(use_adc=True)

        credentials = connector._get_credentials()

        self.assertEqual(connector.project_id, mock_project)
        self.assertEqual(credentials, mock_creds)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.service_account.Credentials.from_service_account_info"
    )
    def test_get_credentials_caches_result(self, mock_from_sa_info):
        """Test _get_credentials() caches credentials"""
        mock_creds = Mock()
        mock_from_sa_info.return_value = mock_creds

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        # First call
        creds1 = connector._get_credentials()
        # Second call should use cached credentials
        creds2 = connector._get_credentials()

        self.assertEqual(creds1, creds2)
        # Should only be called once due to caching
        mock_from_sa_info.assert_called_once()

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.service_account.Credentials.from_service_account_info"
    )
    def test_get_credentials_invalid_json_type(self, mock_from_sa_info):
        """Test _get_credentials() raises ValueError for invalid credentials_json type"""
        connector = GCPMarketplaceConnector(
            project_id="test-project",
            credentials_json="invalid-string",  # Should be dict
        )

        with self.assertRaises(ValueError) as cm:
            connector._get_credentials()
        self.assertIn("dictionary", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.google_auth_default")
    def test_get_credentials_auth_error(self, mock_auth_default):
        """Test _get_credentials() handles GoogleAuthError"""
        mock_auth_default.side_effect = GoogleAuthError("ADC not available")

        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        with self.assertRaises(ValueError) as cm:
            connector._get_credentials()
        self.assertIn("credentials", str(cm.exception).lower())


class TestGCPMarketplaceConnectorClients(TestCase):
    """Test GCP Marketplace connector client initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.credentials_json = {
            "type": "service_account",
            "project_id": "test-project",
        }

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_get_bigquery_client(self, mock_get_creds, mock_bq_client):
        """Test _get_bigquery_client() creates and caches client"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        # First call
        client1 = connector._get_bigquery_client()
        # Second call should return cached client
        client2 = connector._get_bigquery_client()

        self.assertEqual(client1, client2)
        self.assertEqual(client1, mock_client_instance)
        # Should only be called once due to caching
        mock_bq_client.assert_called_once_with(
            credentials=mock_creds, project="test-project", location="US"
        )

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_get_bigquery_client_without_project_id(self, mock_get_creds, mock_bq_client):
        """Test _get_bigquery_client() raises ValueError if project_id not set"""
        connector = GCPMarketplaceConnector(use_adc=True)
        connector.project_id = None  # Ensure project_id is None

        with self.assertRaises(ValueError) as cm:
            connector._get_bigquery_client()
        self.assertIn("project_id", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.AnalyticsHubServiceClient")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_get_analyticshub_client(self, mock_get_creds, mock_ah_client):
        """Test _get_analyticshub_client() creates and caches client"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        mock_ah_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        # First call
        client1 = connector._get_analyticshub_client()
        # Second call should return cached client
        client2 = connector._get_analyticshub_client()

        self.assertEqual(client1, client2)
        self.assertEqual(client1, mock_client_instance)
        # Should only be called once due to caching
        mock_ah_client.assert_called_once_with(credentials=mock_creds)


class TestGCPMarketplaceConnectorAuthentication(TestCase):
    """Test GCP Marketplace connector authentication"""

    def setUp(self):
        """Set up test fixtures"""
        self.credentials_json = {
            "type": "service_account",
            "project_id": "test-project",
        }

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.test_connection"
    )
    def test_authenticate_success(self, mock_test_connection):
        """Test successful authentication"""
        mock_test_connection.return_value = True

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        credentials = {
            "project_id": "new-project",
            "credentials_json": self.credentials_json,
            "location": "EU",
            "use_adc": False,
        }

        result = connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertTrue(connector._authenticated)
        self.assertEqual(connector.project_id, "new-project")
        self.assertEqual(connector.location, "EU")
        mock_test_connection.assert_called_once()

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.test_connection"
    )
    def test_authenticate_with_adc(self, mock_test_connection):
        """Test authentication with ADC"""
        mock_test_connection.return_value = True

        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        credentials = {"project_id": "new-project", "use_adc": True}

        result = connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertTrue(connector._authenticated)
        self.assertTrue(connector.use_adc)

    def test_authenticate_missing_credentials(self):
        """Test authentication raises error if credentials missing"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        with self.assertRaises(ValueError) as cm:
            connector.authenticate({})
        self.assertIn("required", str(cm.exception).lower())

    def test_authenticate_missing_project_id(self):
        """Test authentication raises error if project_id missing"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        credentials = {
            "use_adc": True
            # Missing project_id
        }

        with self.assertRaises(ValueError) as cm:
            connector.authenticate(credentials)
        self.assertIn("project_id", str(cm.exception).lower())

    def test_authenticate_no_auth_method(self):
        """Test authentication raises error if no authentication method provided"""
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        credentials = {
            "project_id": "test-project"
            # Missing both use_adc and credentials_json
        }

        with self.assertRaises(ValueError) as cm:
            connector.authenticate(credentials)
        self.assertIn("use_adc", str(cm.exception).lower())
        self.assertIn("credentials_json", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.test_connection"
    )
    def test_authenticate_resets_clients(self, mock_test_connection):
        """Test authentication resets client instances"""
        mock_test_connection.return_value = True

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        # Set some client instances
        connector._bigquery_client = Mock()
        connector._analyticshub_client = Mock()
        connector._credentials = Mock()

        credentials = {
            "project_id": "new-project",
            "credentials_json": self.credentials_json,
            "use_adc": False,
        }

        connector.authenticate(credentials)

        # Clients should be reset
        self.assertIsNone(connector._bigquery_client)
        self.assertIsNone(connector._analyticshub_client)
        self.assertIsNone(connector._credentials)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.test_connection"
    )
    def test_authenticate_connection_error(self, mock_test_connection):
        """Test authentication raises ConnectionError on test_connection failure"""
        mock_test_connection.side_effect = ConnectionError("Connection failed")

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        credentials = {
            "project_id": "test-project",
            "credentials_json": self.credentials_json,
            "use_adc": False,
        }

        with self.assertRaises(ConnectionError) as cm:
            connector.authenticate(credentials)
        self.assertIn("Google Cloud", str(cm.exception))
        self.assertFalse(connector._authenticated)

    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector.test_connection"
    )
    def test_authenticate_test_connection_returns_false(self, mock_test_connection):
        """Test authentication returns False if test_connection returns False"""
        mock_test_connection.return_value = False

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        credentials = {
            "project_id": "test-project",
            "credentials_json": self.credentials_json,
            "use_adc": False,
        }

        result = connector.authenticate(credentials)

        self.assertFalse(result)
        self.assertFalse(connector._authenticated)


class TestGCPMarketplaceConnectorConnectionTest(TestCase):
    """Test GCP Marketplace connector connection testing"""

    def setUp(self):
        """Set up test fixtures"""
        reset_circuit_breaker_by_name("gcp-marketplace-connector")
        self.credentials_json = {
            "type": "service_account",
            "project_id": "test-project",
        }

    def tearDown(self):
        """Clean up circuit breaker state to prevent cross-test pollution."""
        reset_circuit_breaker_by_name("gcp-marketplace-connector")

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_success(self, mock_get_creds, mock_bq_client):
        """Test successful connection test"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        mock_client_instance.list_datasets.return_value = [Mock()]  # Return at least one dataset
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        result = connector.test_connection()

        self.assertTrue(result)
        mock_client_instance.list_datasets.assert_called_once_with(max_results=1)

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_not_found_error(self, mock_get_creds, mock_bq_client):
        """Test connection test raises NotFoundError for 404"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        error = GoogleAPIError("Project not found")
        error.code = 404
        mock_client_instance.list_datasets.side_effect = error
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        with self.assertRaises(NotFoundError) as cm:
            connector.test_connection()
        self.assertIn("not found", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_permission_error(self, mock_get_creds, mock_bq_client):
        """Test connection test raises PermissionError for 403"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        error = GoogleAPIError("Permission denied")
        error.code = 403
        mock_client_instance.list_datasets.side_effect = error
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        with self.assertRaises(PermissionError) as cm:
            connector.test_connection()
        self.assertIn("permission", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_other_api_error(self, mock_get_creds, mock_bq_client):
        """Test connection test raises ConnectionError for other API errors"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        error = GoogleAPIError("Internal error")
        error.code = 500
        mock_client_instance.list_datasets.side_effect = error
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        with self.assertRaises(ConnectionError) as cm:
            connector.test_connection()
        # Error message should indicate transient error after retries
        err = str(cm.exception)
        self.assertTrue(
            "Transient error" in err or "GCP project" in err,
            f"Expected transient/GCP error, got: {err}",
        )

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_auth_error(self, mock_get_creds, mock_bq_client):
        """Test connection test raises ConnectionError for auth errors"""
        mock_get_creds.side_effect = GoogleAuthError("Authentication failed")
        mock_bq_client.return_value = Mock()

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        with self.assertRaises(ConnectionError) as cm:
            connector.test_connection()
        self.assertIn("Authentication", str(cm.exception))

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_value_error(self, mock_get_creds, mock_bq_client):
        """Test connection test re-raises ValueError"""
        mock_get_creds.side_effect = ValueError("Missing project_id")

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        with self.assertRaises(ValueError) as cm:
            connector.test_connection()
        self.assertIn("project_id", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.gcp_marketplace_connector.bigquery.Client")
    @patch(
        "hub.apps.integrations.connectors.gcp_marketplace_connector.GCPMarketplaceConnector._get_credentials"
    )
    def test_test_connection_uses_circuit_breaker(self, mock_get_creds, mock_bq_client):
        """Test connection test uses circuit breaker"""
        mock_creds = Mock()
        mock_get_creds.return_value = mock_creds
        mock_client_instance = Mock()
        mock_client_instance.list_datasets.return_value = []
        mock_bq_client.return_value = mock_client_instance

        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=self.credentials_json
        )

        # Mock circuit breaker call
        with patch.object(connector._circuit_breaker, "call") as mock_cb_call:
            mock_cb_call.return_value = True
            result = connector.test_connection()

            self.assertTrue(result)
            mock_cb_call.assert_called_once()


class TestGCPMarketplaceConnectorNotImplementedMethods(TestCase):
    """Test that unimplemented methods raise NotImplementedError"""

    def setUp(self):
        """Set up test fixtures"""
        reset_circuit_breaker_by_name("gcp-marketplace-connector")
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    # Note: list_listings(), get_listing(), and list_resources() are now implemented
    # Tests for these methods are in test_gcp_marketplace_connector_discovery.py

    # Note: download_resource() is now implemented
    # Tests for this method are in test_gcp_marketplace_connector_pull.py

    # Note: map_to_hub_asset() and sync_pull() are now implemented
    # Tests for these methods are in test_gcp_marketplace_connector_pull.py


class TestGCPMarketplaceConnectorPushOperations(TestCase):
    """Test that push operations raise NotImplementedError"""

    def setUp(self):
        """Set up test fixtures"""
        reset_circuit_breaker_by_name("gcp-marketplace-connector")
        self.connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

    def test_create_listing_not_implemented(self):
        """Test create_listing() raises NotImplementedError"""
        listing = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing)
        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_update_listing_not_implemented(self):
        """Test update_listing() raises NotImplementedError"""
        listing = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test-id", listing)
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_publish_resource_not_implemented(self):
        """Test publish_resource() raises NotImplementedError"""
        resource = Mock()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test-id", resource)
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_map_from_hub_asset_not_implemented(self):
        """Test map_from_hub_asset() raises NotImplementedError"""
        asset_data = {}
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset(asset_data)
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_sync_push_not_implemented(self):
        """Test sync_push() raises NotImplementedError"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_sync_push_with_empty_asset_ids(self):
        """Test sync_push() error handling with empty asset_ids list"""
        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.sync_push([])

    def test_sync_push_with_none_asset_ids(self):
        """Test sync_push() error handling with None asset_ids"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.sync_push(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_create_listing_with_none(self):
        """Test create_listing() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.create_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_update_listing_with_empty_id(self):
        """Test update_listing() error handling with empty ID"""
        from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

        listing = MarketplaceListing(
            marketplace_id="test-listing",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test",
        )
        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.update_listing("", listing)

    def test_update_listing_with_none_id(self):
        """Test update_listing() error handling with None ID"""
        from hub.apps.integrations.base import MarketplaceListing, MarketplaceType

        listing = MarketplaceListing(
            marketplace_id="test-listing",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test",
        )
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.update_listing(None, listing)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_publish_resource_with_empty_package_id(self):
        """Test publish_resource() error handling with empty package ID"""
        from hub.apps.integrations.base import MarketplaceResource

        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
        )
        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.publish_resource("", resource)

    def test_map_from_hub_asset_with_none(self):
        """Test map_from_hub_asset() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.map_from_hub_asset(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_map_from_hub_asset_with_empty_dict(self):
        """Test map_from_hub_asset() error handling with empty dict"""
        with self.assertRaises(NotImplementedError):
            self.connector.map_from_hub_asset({})
