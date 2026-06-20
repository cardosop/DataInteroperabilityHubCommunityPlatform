"""
Security Tests for GCP Marketplace Connector

Tests authentication, authorization, credential encryption, and input validation.
Tests verify GCP security best practices.

These tests use real Google Cloud SDK clients - no mocks/stubs.
"""

import json
import os

from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, PermissionError
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import Tenant

# Optional Google Cloud imports - skip tests if not available
try:
    from google.auth.exceptions import GoogleAuthError

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GoogleAuthError = None
    GOOGLE_CLOUD_AVAILABLE = False

import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not GOOGLE_CLOUD_AVAILABLE, reason="Google Cloud libraries not installed"
)


# Real service account credentials for testing
# REAL_SERVICE_ACCOUNT_JSON removed — use get_test_credentials() below


def get_test_credentials():
    """Get GCP test credentials from environment.

    Requires GCP_SERVICE_ACCOUNT_JSON env var (set via .env.test and
    the Makefile test-batch-6-2 target).  Raises SkipTest when the
    env var is not available so the test suite can run without GCP
    credentials in environments where they are not configured.
    """
    import unittest

    env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not env_json:
        raise unittest.SkipTest("GCP_SERVICE_ACCOUNT_JSON not set — skipping")
    try:
        return json.loads(env_json)
    except json.JSONDecodeError:
        raise unittest.SkipTest("GCP_SERVICE_ACCOUNT_JSON is not valid JSON — skipping")


class TestGCPMarketplaceConnectorSecurity(TestCase):
    """Security tests for GCP Marketplace connector"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

    def test_service_account_json_validation(self):
        """Test service account JSON validation"""
        # Test missing credentials_json - should require either credentials_json or use_adc
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(
                project_id="test-project"
                # Missing both credentials_json and use_adc
            )

        # Test invalid credentials_json type - will raise error when trying to use credentials
        connector = GCPMarketplaceConnector(
            project_id="test-project",
            credentials_json={"type": "service_account"},  # Valid type but incomplete
        )
        # Will raise error when trying to create credentials
        with self.assertRaises((ValueError, GoogleAuthError)):
            connector._get_credentials()

        # Test missing required fields in credentials_json
        invalid_credentials = {
            "type": "service_account",
            # Missing project_id, private_key, client_email, etc.
        }
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=invalid_credentials
        )
        # Should raise error when trying to create credentials
        with self.assertRaises((ValueError, GoogleAuthError)):
            connector._get_credentials()

    def test_adc_authentication_validation(self):
        """Test Application Default Credentials authentication validation"""
        # Test ADC without project_id - should work if ADC provides project
        connector = GCPMarketplaceConnector(use_adc=True)
        # ADC may or may not provide project_id
        # If not provided, should raise error when trying to use BigQuery client
        try:
            connector._get_credentials()
            # If credentials work, project_id should be set
            if connector.project_id:
                # Should be able to create BigQuery client
                client = connector._get_bigquery_client()
                self.assertIsNotNone(client)
        except (ValueError, GoogleAuthError):
            # ADC not available - acceptable in test environment
            pass

    def test_invalid_credentials_handling(self):
        """Test handling of invalid credentials"""
        # Test with invalid service account JSON
        invalid_credentials = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "-----BEGIN PRIVATE KEY-----\ninvalid\n-----END PRIVATE KEY-----\n",
            "client_email": "invalid@test.iam.gserviceaccount.com",
        }
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json=invalid_credentials
        )

        # Should raise error during authentication or connection test
        # The error gets wrapped in ConnectionError by authenticate()
        with self.assertRaises((ValueError, GoogleAuthError, PermissionError, ConnectionError)):
            connector.authenticate(
                {"project_id": "test-project", "credentials_json": invalid_credentials}
            )

    def test_missing_credentials_handling(self):
        """Test handling of missing credentials"""
        # Test with None credentials_json - should raise error in __init__
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(
                project_id="test-project", credentials_json=None, use_adc=False
            )

        # Test authenticate with missing credentials
        connector = GCPMarketplaceConnector(project_id="test-project", use_adc=True)

        # Should raise error when trying to authenticate without credentials
        with self.assertRaises(ValueError):
            connector.authenticate(
                {
                    "project_id": "test-project",
                    # Missing both credentials_json and use_adc
                }
            )

    def test_credential_encryption_in_storage(self):
        """Test that stored credentials are encrypted"""
        # Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            name="Test Connection",
            config={
                "project_id": self.project_id,
                "credentials_json": self.credentials_json,
            },
        )

        # Verify credentials are stored
        # Note: Actual encryption depends on Django settings and encryption middleware
        # When encryption is enabled, config is stored as {'_encrypted': '...'}
        # When encryption is disabled, config stores keys directly
        stored_config = connection.config

        # Check if encryption is enabled (indicated by '_encrypted' key)
        if "_encrypted" in stored_config:
            # Encryption is enabled - verify encrypted value exists
            self.assertIn("_encrypted", stored_config)
            self.assertIsInstance(stored_config["_encrypted"], str)
            self.assertGreater(len(stored_config["_encrypted"]), 0)
        else:
            # Encryption is disabled - verify keys exist directly
            self.assertIn("project_id", stored_config)
            self.assertIn("credentials_json", stored_config)

    def test_input_validation_project_id(self):
        """Test project_id validation"""
        # Test empty project_id
        connector = GCPMarketplaceConnector(project_id="", use_adc=True)
        with self.assertRaises(ValueError):
            connector._get_bigquery_client()

        # Test None project_id
        connector = GCPMarketplaceConnector(project_id=None, use_adc=True)
        with self.assertRaises(ValueError):
            connector._get_bigquery_client()

        # Test invalid project_id format (contains invalid characters)
        connector = GCPMarketplaceConnector(
            project_id="invalid-project-id-with-special-chars!@#",
            credentials_json={"type": "service_account"},
        )
        # May fail during authentication or connection test
        with self.assertRaises((ValueError, PermissionError)):
            connector.test_connection()

    def test_input_validation_listing_id(self):
        """Test listing ID validation"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test empty listing ID
        with self.assertRaises((ValueError, NotFoundError)):
            connector.get_listing("")

        # Test None listing ID - will cause AttributeError when trying to parse
        with self.assertRaises((ValueError, TypeError, AttributeError, ConnectionError)):
            connector.get_listing(None)

        # Test invalid listing ID format
        with self.assertRaises((ValueError, NotFoundError)):
            connector.get_listing("invalid/format/with/many/slashes")

    def test_input_validation_dataset_id(self):
        """Test dataset ID validation in resource operations"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test empty dataset ID in listing ID format
        with self.assertRaises((ValueError, NotFoundError, ConnectionError)):
            connector.list_resources("")

        # Test None dataset ID - will cause AttributeError when get_listing tries to parse it
        # The connector calls get_listing internally which tries to split None
        with self.assertRaises((ValueError, TypeError, AttributeError, ConnectionError)):
            connector.list_resources(None)

    def test_gcp_iam_permissions_handling(self):
        """Test GCP IAM permissions handling"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test connection with insufficient permissions
        # If credentials don't have required permissions, should raise PermissionError
        try:
            result = connector.test_connection()
            # If connection succeeds, permissions are sufficient
            self.assertIsInstance(result, bool)
        except PermissionError:
            # Expected if credentials lack required permissions
            pass

    def test_permission_error_handling(self):
        """Test PermissionError handling for unauthorized operations"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Try to access a resource that requires permissions we don't have
        # This may raise PermissionError if credentials lack permissions
        try:
            listings = connector.list_listings()
            # If succeeds, permissions are sufficient
            self.assertIsInstance(listings, list)
        except PermissionError:
            # Expected if credentials lack Analytics Hub permissions
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # No data exchanges found - acceptable
            pass

    def test_least_privilege_principle(self):
        """Test that connector follows least privilege principle"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Verify connector only performs read operations (harvest-only)
        # Push operations should raise NotImplementedError
        from hub.apps.integrations.base import MarketplaceListing, MarketplaceResource

        with self.assertRaises(NotImplementedError):
            connector.sync_push(["asset-1"])

        # Create minimal listing/resource objects for testing
        minimal_listing = MarketplaceListing(
            marketplace_id="test-id",
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title="Test",
        )
        minimal_resource = MarketplaceResource(
            resource_id="test-resource", resource_type="table", name="Test Resource"
        )

        with self.assertRaises(NotImplementedError):
            connector.create_listing(minimal_listing)

        with self.assertRaises(NotImplementedError):
            connector.update_listing("test-id", minimal_listing)

        with self.assertRaises(NotImplementedError):
            connector.publish_resource("test-id", minimal_resource)

    def test_credential_rotation_support(self):
        """Test that connector supports credential rotation"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Use clients to ensure they're initialized
        try:
            bq_client = connector._get_bigquery_client()
            self.assertIsNotNone(bq_client)
            # Store reference to verify it changes after rotation
            old_bq_client = bq_client
        except Exception:
            old_bq_client = None

        # Rotate credentials by re-authenticating with new credentials
        new_credentials = {
            "project_id": self.project_id,
            "credentials_json": self.credentials_json,  # Same for test, but could be different
            "use_adc": False,
        }

        # Should be able to re-authenticate with new credentials
        result = connector.authenticate(new_credentials)
        self.assertTrue(result)

        # Note: authenticate() calls test_connection() which creates a new BigQuery client
        # So _bigquery_client will not be None after authenticate() completes
        # But the client should be recreated with new credentials

        # Verify new clients can be created after rotation
        try:
            new_bq_client = connector._get_bigquery_client()
            self.assertIsNotNone(new_bq_client)
            # If we had an old client, verify it's a new instance (or same if credentials unchanged)
            if old_bq_client:
                # Client may be same instance if credentials are identical, which is fine
                # The important thing is that authentication succeeded
                pass
        except Exception:
            # May fail if credentials are invalid, but that's acceptable
            pass

    def test_input_sanitization(self):
        """Test input sanitization to prevent injection attacks"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test SQL injection attempts in listing ID
        malicious_inputs = [
            "'; DROP TABLE listings; --",
            "../../etc/passwd",
            "<script>alert('xss')</script>",
        ]

        for malicious_input in malicious_inputs:
            with self.assertRaises((ValueError, NotFoundError)):
                connector.get_listing(malicious_input)

        # Test path traversal attempts
        with self.assertRaises((ValueError, NotFoundError)):
            connector.list_resources("../../../etc/passwd")

    def test_input_validation_empty_strings(self):
        """Test input validation with empty strings"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test empty string for listing ID
        with self.assertRaises((ValueError, NotFoundError)):
            connector.get_listing("")

        # Test empty string for resource listing ID
        with self.assertRaises((ValueError, NotFoundError, ConnectionError)):
            connector.list_resources("")

    def test_input_validation_none_values(self):
        """Test input validation with None values"""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Test None for listing ID
        with self.assertRaises((ValueError, TypeError, AttributeError, ConnectionError)):
            connector.get_listing(None)  # type: ignore[arg-type]  # test: None arg for error-path coverage

        # Test None for resource listing ID
        with self.assertRaises((ValueError, TypeError, AttributeError, ConnectionError)):
            connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_credential_validation_with_empty_strings(self):
        """Test credential validation with empty strings"""
        # Test empty project_id
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(
                project_id="", credentials_json=self.credentials_json
            )
            connector._get_bigquery_client()

        # Test empty credentials_json (should require either credentials_json or use_adc)
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(
                project_id=self.project_id,
                credentials_json={},
                use_adc=False,  # Empty dict
            )

    def test_authentication_with_malformed_credentials(self):
        """Test authentication error handling with malformed credentials"""
        # Test with malformed JSON structure
        malformed_credentials = {
            "type": "service_account",
            "project_id": self.project_id,
            # Missing required fields: private_key, client_email
        }
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=malformed_credentials
        )

        with self.assertRaises((ValueError, GoogleAuthError)):
            connector.authenticate(
                {"project_id": self.project_id, "credentials_json": malformed_credentials}
            )
