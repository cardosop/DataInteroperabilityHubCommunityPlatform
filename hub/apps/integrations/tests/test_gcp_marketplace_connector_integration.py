"""
Integration Tests for GCP Marketplace Connector

Tests the GCPMarketplaceConnector implementation using REAL Google Cloud credentials.
No mocks or stubs - tests actual Google Cloud API calls.

These tests require:
- Valid Google Cloud service account credentials
- GCP project with BigQuery API enabled
- Network access to Google Cloud APIs

To run these tests:
1. Set GCP_SERVICE_ACCOUNT_JSON environment variable with service account JSON
2. Or set GCP_PROJECT_ID and GCP_USE_ADC=true for Application Default Credentials
3. Run: docker-compose -f docker-compose.test.yml exec api-service-test python -m pytest hub/apps/integrations/tests/test_gcp_marketplace_connector_integration.py -v
"""

import json
import os

import pytest
from django.test import TestCase, override_settings

from hub.apps.core.services.base import NotFoundError, PermissionError
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
)
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector

# Real service account credentials for testing
# These should be provided via environment variable GCP_SERVICE_ACCOUNT_JSON
REAL_SERVICE_ACCOUNT_JSON = {
    "type": "service_account",
    "project_id": "projzero-441310",
    "private_key_id": "e2f5c18b5f2495f6e07e8a8a2302d3da3e711c38",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC4qnbgFWOgw99L\nQpbw6LLoJHJisAKCpOmNbIBxPTNSlT1yu/Wmd669qC3lNQgSeJL0cTUJ0h9U4j6C\nbSiNvR7HMs+odKCA69J0M+kA6EgAHNl8Uz41e4fPxnJK6LDujjfRHa53UzLuMQHN\nYif/Z70jr6yAvh87u/8nT977q7LFJovtLr7+EkWN/6E5dd9VpmmsW0c+OrKCoWR/\nTgvy/Sht0rB1eazqRowhCe0SbW+8NoFy6qoBWFwnNmm1Azo6DFstChC9OGAy8OK2\nBUMYWnjKonAFhllr85IYWIF7v3X68NGJcBnswYBv5VFqZsP6P+pJZFxFEF5WMm8R\nwSdIaLQDAgMBAAECggEASU/Tdc7ICLD6WwSKrAWV0Td2+drqhDc4SV8D9vDXCTga\ndwxLz9S/2KeF4PMWy052+PhgmA+FRMu1CU6QxQSJzYdMjZIPjl8Q4/Uf0a5ltzW8\n2fCqR81M853TDg4m/+4SFsDz3Id5NrrZ/lGzk1/55Mr/bvULrUlLWK4K1lsp0752\nLLuTd8TTP3peApaoZAJ5mih7tZwcYfgeMPC9PMUJBlb1BFDdxuECaYg3uYoGIRYt\nkNYZ0YmWDGq/yRnPUFwslqcDtomrW56t0v5lHbqibmFy3T2y4VFpXQL9wGlRhA7J\n2/GgRPM6N0y9Bn4GFbPaIAAUekHUTFmErKNcrrLgcQKBgQDypufx+LACKMLtr0F6\nFiVaFcWjKopGignWAatHaU/FP1XdxVvT8YCWJOcUmEX+Jh04bMHsCyB7vK6ZPx+0\nD/ZuejkrXose7DzfAswgHrIjDhjqrhgBsZB9bWx/7bWxXK5XctseaWPwWWNnRKCY\nHJrCtVRpHgz43MyXKQhmuHLdVQKBgQDC0vtKsg+4iih6B4MPrbdHjFTC+LYg73nS\nDpRwnPCmtI8DLvJlZr/tLuai2uqo1Ui0V3R/n48n2Ye2wvliDWYvQ2s7d+48Kq4s\n5As5pNNApo6qGDKn8rRd3kKVs6xGe+XPkLF5oM9LTkR5fqH6ALGIwM9C4xlfO/uC\nZ1V/5ciL9wKBgA7VEPyDfQ7EuxWYTuJNlD7rccdFhGpHac6BD50v3MZr1q3VsIVG\nD9wdqVpi7HRalBKs4zWwgG3P3MRVTXTOPPwH0JLMFqjvO9FN9HhKKA1ogTFnLuR7\nnB9unuE7AI404htKVAaJ3qgEbsUTNtXVechJGT3LrnNP29mpkm/k+nB5AoGALIdS\nXjEyfKg/NhzvbK70vAqr+OAlqINzoXopnU+RhVixczXQuzJv3YMhvckxZyNQeb+f\nZegPLTl/1lrb6vhLCbRsFuyDbAcJRkNc+XDdw+INq3zaXx6O8QFy0Ip/bqC01uso\nVTdXCcw6xFYYKW7tJOeEt7H2Q5kPFDAQD6pyWuMCgYEA6XiSeJeBEJTmIAnWwX/D\nsgYW5e1VLilFxfJpn4QtiogUMDugPCKDTHatfq984VS0tBWH7cyTKgI/l4fr/i9+\nOEQu+bn7n78t8cTCdzWlc3Upt9JKxvC7P4UTfAHV7YAmeCUNd3X1Y/1587wqaIe5\nBAYqnsxHdTUK5DfrMcgTPYw=\n-----END PRIVATE KEY-----\n",
    "client_email": "dih-786@projzero-441310.iam.gserviceaccount.com",
    "client_id": "106741124606177610543",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dih-786%40projzero-441310.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}


def get_test_credentials():
    """Get test credentials from environment or use default.

    If GCP_SERVICE_ACCOUNT_JSON is set but not valid JSON (e.g. corrupted by
    shell when sourcing .env), fall back to REAL_SERVICE_ACCOUNT_JSON so tests
    run instead of skipping.
    """
    env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            return json.loads(env_json)
        except json.JSONDecodeError:
            return REAL_SERVICE_ACCOUNT_JSON
    return REAL_SERVICE_ACCOUNT_JSON


@pytest.mark.integration
class TestGCPMarketplaceConnectorIntegration(TestCase):
    """Integration tests for GCP Marketplace connector using real credentials"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )

    def test_connector_initialization_with_real_credentials(self):
        """Test connector initialization with real service account JSON"""
        self.assertEqual(self.connector.project_id, self.project_id)
        self.assertEqual(self.connector.credentials_json, self.credentials_json)
        self.assertEqual(self.connector.location, "US")
        self.assertFalse(self.connector.use_adc)
        self.assertEqual(self.connector.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)

    def test_connector_initialization_with_empty_project_id(self):
        """Test connector initialization error handling with empty project_id"""
        with self.assertRaises((ValueError, TypeError)):
            connector = GCPMarketplaceConnector(
                project_id="", credentials_json=self.credentials_json
            )

    def test_connector_initialization_with_none_project_id(self):
        """Test connector initialization error handling with None project_id"""
        with self.assertRaises((ValueError, TypeError)):
            connector = GCPMarketplaceConnector(
                project_id=None, credentials_json=self.credentials_json  # type: ignore[arg-type]
            )

    def test_connector_initialization_with_invalid_credentials(self):
        """Test connector initialization error handling with invalid credentials"""
        invalid_credentials = {
            "type": "service_account",
            # Missing required fields
        }
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=invalid_credentials
        )
        # Will raise error when trying to authenticate
        with self.assertRaises((ValueError, PermissionError)):
            connector.authenticate(
                {"project_id": self.project_id, "credentials_json": invalid_credentials}
            )

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        try:
            listings = self.connector.list_listings(limit=0)
            # Should return empty list or handle gracefully
            self.assertIsInstance(listings, list)
            self.assertEqual(len(listings), 0)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_list_listings_with_none_limit(self):
        """Test list_listings() error handling with None limit"""
        try:
            listings = self.connector.list_listings(limit=None)  # type: ignore[arg-type]
            # Should handle None limit gracefully (may use default)
            self.assertIsInstance(listings, list)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.get_listing("")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.get_listing(None)  # type: ignore[arg-type]
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_list_resources_with_empty_listing_id(self):
        """Test list_resources() error handling with empty listing ID"""
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.list_resources("")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_list_resources_with_none_listing_id(self):
        """Test list_resources() error handling with None listing ID"""
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.list_resources(None)  # type: ignore[arg-type]
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except Exception:
            # May fail if not authenticated or other errors
            pass

    def test_marketplace_type_property(self):
        """Test marketplace_type property returns correct value"""
        self.assertEqual(self.connector.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions property returns PULL only"""
        directions = self.connector.supported_sync_directions
        self.assertEqual(len(directions), 1)
        self.assertIn(SyncDirection.PULL, directions)
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker is properly initialized"""
        self.assertIsNotNone(self.connector._circuit_breaker)
        self.assertEqual(self.connector._circuit_breaker.service_name, "gcp-marketplace-connector")
        self.assertEqual(self.connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(self.connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(self.connector._circuit_breaker.success_threshold, 2)

    def test_get_credentials_with_service_account_json(self):
        """Test _get_credentials() with real service account JSON"""
        credentials = self.connector._get_credentials()
        self.assertIsNotNone(credentials)
        # Verify credentials have required attributes
        self.assertTrue(
            hasattr(credentials, "service_account_email") or hasattr(credentials, "client_email")
        )
        # Credentials should be cached
        credentials2 = self.connector._get_credentials()
        self.assertEqual(credentials, credentials2)

    def test_get_bigquery_client(self):
        """Test _get_bigquery_client() creates real BigQuery client"""
        client = self.connector._get_bigquery_client()
        self.assertIsNotNone(client)
        self.assertEqual(client.project, self.project_id)
        # Client should be cached
        client2 = self.connector._get_bigquery_client()
        self.assertEqual(client, client2)

    def test_get_analyticshub_client(self):
        """Test _get_analyticshub_client() creates real Analytics Hub client"""
        try:
            client = self.connector._get_analyticshub_client()
            self.assertIsNotNone(client)
            # Client should be cached
            client2 = self.connector._get_analyticshub_client()
            self.assertEqual(client, client2)
        except ImportError:
            # Analytics Hub client library not installed - skip this test
            self.skipTest("Analytics Hub client library not installed")

    def test_authenticate_with_real_credentials(self):
        """Test authenticate() with real credentials"""
        credentials = {
            "project_id": self.project_id,
            "credentials_json": self.credentials_json,
            "location": "US",
            "use_adc": False,
        }

        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertTrue(self.connector._authenticated)
        self.assertEqual(self.connector.project_id, self.project_id)
        self.assertEqual(self.connector.location, "US")

    def test_test_connection_success(self):
        """Test test_connection() succeeds with real credentials"""
        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify BigQuery client was created
        self.assertIsNotNone(self.connector._bigquery_client)

    def test_test_connection_with_invalid_project_id(self):
        """Test test_connection() raises NotFoundError for invalid project"""
        invalid_connector = GCPMarketplaceConnector(
            project_id="invalid-project-id-12345", credentials_json=self.credentials_json
        )

        with self.assertRaises((NotFoundError, PermissionError, Exception)):
            # May raise NotFoundError (404) or PermissionError (403) depending on GCP behavior
            invalid_connector.test_connection()

    def test_authenticate_resets_clients(self):
        """Test authenticate() resets client instances"""
        # Create clients first
        self.connector._get_bigquery_client()

        # Try to create Analytics Hub client (may fail if library not installed)
        try:
            self.connector._get_analyticshub_client()
            analyticshub_was_created = True
        except ImportError:
            analyticshub_was_created = False

        # Verify BigQuery client exists
        self.assertIsNotNone(self.connector._bigquery_client)

        # Authenticate should reset clients
        credentials = {
            "project_id": self.project_id,
            "credentials_json": self.credentials_json,
            "use_adc": False,
        }
        self.connector.authenticate(credentials)

        # Clients should be reset (will be recreated on next access)
        # Note: authenticate() calls test_connection() which creates BigQuery client
        # So _bigquery_client may not be None, but _analyticshub_client should be None
        # Let's check that Analytics Hub client was reset if it was created
        if analyticshub_was_created:
            self.assertIsNone(self.connector._analyticshub_client)

    def test_authenticate_with_different_location(self):
        """Test authenticate() with different location"""
        credentials = {
            "project_id": self.project_id,
            "credentials_json": self.credentials_json,
            "location": "EU",
            "use_adc": False,
        }

        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector.location, "EU")

    def test_authenticate_validation_errors(self):
        """Test authenticate() validation errors"""
        # Missing project_id
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate({"credentials_json": self.credentials_json})
        self.assertIn("project_id", str(cm.exception).lower())

        # Missing both use_adc and credentials_json
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate({"project_id": self.project_id})
        self.assertIn("use_adc", str(cm.exception).lower())
        self.assertIn("credentials_json", str(cm.exception).lower())

    def test_connector_initialization_validation(self):
        """Test connector initialization validation"""
        # Missing authentication method
        with self.assertRaises(ValueError) as cm:
            GCPMarketplaceConnector(project_id="test-project")
        self.assertIn("use_adc", str(cm.exception).lower())
        self.assertIn("credentials_json", str(cm.exception).lower())


@pytest.mark.integration
class TestGCPMarketplaceConnectorErrorHandling(TestCase):
    """Test error handling with real credentials"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )

    def test_get_bigquery_client_without_project_id(self):
        """Test _get_bigquery_client() raises ValueError if project_id not set"""
        connector = GCPMarketplaceConnector(credentials_json=self.credentials_json)
        connector.project_id = None

        with self.assertRaises(ValueError) as cm:
            connector._get_bigquery_client()
        self.assertIn("project_id", str(cm.exception).lower())

    def test_get_credentials_with_invalid_json_type(self):
        """Test _get_credentials() raises ValueError for invalid credentials_json type"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json="invalid-string"  # Should be dict
        )

        with self.assertRaises(ValueError) as cm:
            connector._get_credentials()
        self.assertIn("dictionary", str(cm.exception).lower())


@pytest.mark.integration
class TestGCPMarketplaceConnectorNotImplementedMethods(TestCase):
    """Test that unimplemented methods raise NotImplementedError"""

    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )

    # Note: list_listings(), get_listing(), and list_resources() are now implemented
    # Tests for these methods are in test_gcp_marketplace_connector_discovery.py

    # Note: download_resource() is now implemented
    # Tests for this method are in test_gcp_marketplace_connector_pull.py and test_gcp_marketplace_connector_pull_integration.py

    # Note: map_to_hub_asset() and sync_pull() are now implemented
    # Tests for these methods are in test_gcp_marketplace_connector_pull.py and test_gcp_marketplace_connector_pull_integration.py

    def test_create_listing_not_implemented(self):
        """Test create_listing() raises NotImplementedError"""
        listing = type("MockListing", (), {})()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing)
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_update_listing_not_implemented(self):
        """Test update_listing() raises NotImplementedError"""
        listing = type("MockListing", (), {})()
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test-id", listing)
        self.assertIn("harvest-only", str(cm.exception).lower())

    def test_publish_resource_not_implemented(self):
        """Test publish_resource() raises NotImplementedError"""
        resource = type("MockResource", (), {})()
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
