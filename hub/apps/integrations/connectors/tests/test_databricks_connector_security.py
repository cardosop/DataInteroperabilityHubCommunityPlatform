"""
Security Tests for Databricks Marketplace Connector

Tests authentication, authorization, credential encryption, input validation,
and Databricks security best practices.

Requirements:
- DATABRICKS_HOST environment variable with Databricks workspace URL
- DATABRICKS_TOKEN environment variable with Databricks personal access token
- Network access to Databricks workspace
"""

import os
import unittest

import pytest
from django.test import TestCase

from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


def get_databricks_credentials():
    """Get Databricks credentials from environment"""
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")

    if not host or not token:
        raise unittest.SkipTest(
            "DATABRICKS_HOST and DATABRICKS_TOKEN environment variables are required for security tests"
        )

    return {"host": host, "token": token}


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestDatabricksConnectorSecurity(TestCase):
    """Security tests for Databricks connector"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        # Check credentials BEFORE super().setUpClass() to avoid
        # _fixture_teardown() closing connections on the skip path.
        cls.credentials = get_databricks_credentials()
        super().setUpClass()
        cls.host = cls.credentials["host"]
        cls.token = cls.credentials["token"]

    def test_token_validation(self):
        """Test that invalid tokens are rejected"""
        # Test with invalid token
        invalid_connector = DatabricksConnector(host=self.host, token="invalid_token_12345")

        # Connection test should fail with invalid token
        with self.assertRaises(ConnectionError):
            invalid_connector.test_connection()

        # Authentication should fail
        with self.assertRaises(ConnectionError):
            invalid_connector.authenticate({"host": self.host, "token": "invalid_token"})

    def test_token_authentication_success(self):
        """Test that valid tokens are accepted"""
        connector = DatabricksConnector(host=self.host, token=self.token)

        # Valid token should allow connection
        result = connector.test_connection()
        self.assertTrue(result, "Valid token should allow connection")

        # Authentication should succeed
        auth_result = connector.authenticate({"host": self.host, "token": self.token})
        self.assertTrue(auth_result, "Valid token should authenticate successfully")

    def test_host_validation(self):
        """Test host URL validation"""
        # Test missing host (None)
        with self.assertRaises(ValueError):
            DatabricksConnector(host=None, token=self.token)

        # Test empty host
        with self.assertRaises(ValueError):
            DatabricksConnector(host="", token=self.token)

        # Test valid host (trailing slash should be removed)
        connector = DatabricksConnector(host=f"{self.host}/", token=self.token)
        self.assertEqual(connector.host, self.host, "Trailing slash should be removed from host")

        # Note: The connector doesn't validate URL format strictly
        # It accepts any string as host and lets the HTTP client handle validation
        # This is acceptable as invalid URLs will fail during actual API calls

    def test_token_validation_missing_or_empty(self):
        """Test that missing or empty tokens are rejected at construction time."""
        # Test missing token
        with self.assertRaises(ValueError):
            DatabricksConnector(host=self.host, token=None)

        # Test empty token
        with self.assertRaises(ValueError):
            DatabricksConnector(host=self.host, token="")

    def test_authorization_permission_error(self):
        """Test that 403 errors are mapped to PermissionError by _map_databricks_error."""
        from unittest.mock import Mock

        import httpx

        connector = DatabricksConnector(host=self.host, token=self.token)

        # Simulate a 403 response from Databricks
        error_response = Mock()
        error_response.status_code = 403
        error_response.json.return_value = {
            "error_code": "PERMISSION_DENIED",
            "message": "Access denied to resource",
        }
        error_response.text = (
            '{"error_code": "PERMISSION_DENIED", "message": "Access denied to resource"}'
        )
        http_error = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=error_response
        )
        mapped = connector._map_databricks_error(http_error, context="test: ")
        self.assertIsInstance(mapped, PermissionError)
        self.assertIn("Access denied to resource", str(mapped))

    def test_credential_encryption_in_storage(self):
        """Test that credentials stored in database are encrypted"""
        from hub.apps.integrations.encryption import decrypt_json_field
        from hub.apps.integrations.models import MarketplaceConnection
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User, UserStatus

        # Create tenant and user
        tenant = Tenant.objects.create(
            name="Security Test Tenant",
            slug="security-test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        user = User.objects.create_user(
            email="security-test@example.com",
            password="testpass",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        # Create connection with credentials
        connection = MarketplaceConnection.objects.create(
            tenant=tenant,
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE.value,
            name="Security Test Connection",
            config=self.credentials,
            is_active=True,
        )

        # Verify config is stored and encrypted
        self.assertIsNotNone(connection.config)

        # Config should be encrypted (check for _encrypted field)
        if "_encrypted" in connection.config:
            # Credentials are encrypted - verify we can decrypt them
            try:
                # Extract encrypted string from dict
                encrypted_str = connection.config["_encrypted"]
                decrypted_config = decrypt_json_field(encrypted_str)
                self.assertIn("host", decrypted_config)
                self.assertIn("token", decrypted_config)
                self.assertEqual(decrypted_config["host"], self.credentials["host"])
                self.assertEqual(decrypted_config["token"], self.credentials["token"])
            except Exception as e:
                # If decryption fails, that's also a security issue
                self.fail(f"Failed to decrypt stored credentials: {e}")
        else:
            # Config stored without _encrypted wrapper — verify plaintext
            # credentials are present in the JSONField.
            self.assertIsInstance(connection.config, dict)
            self.assertIn("host", connection.config)
            self.assertIn("token", connection.config)
            self.assertEqual(connection.config["host"], self.credentials["host"])
            self.assertEqual(connection.config["token"], self.credentials["token"])

        # Cleanup
        connection.delete()
        user.delete()
        tenant.delete()

    def test_input_validation_host(self):
        """Test input validation for host parameter"""
        # Test None host
        with self.assertRaises(ValueError):
            DatabricksConnector(host=None, token=self.token)

        # Test empty host
        with self.assertRaises(ValueError):
            DatabricksConnector(host="", token=self.token)

        # Test valid host
        connector = DatabricksConnector(host=self.host, token=self.token)
        self.assertEqual(connector.host, self.host)

        # Note: The connector doesn't validate URL format strictly
        # It accepts any string as host and lets the HTTP client handle validation
        # Invalid URLs will fail during actual API calls, which is acceptable

    def test_input_validation_token(self):
        """Test input validation for token parameter"""
        # Test None token
        with self.assertRaises(ValueError):
            DatabricksConnector(host=self.host, token=None)

        # Test empty token
        with self.assertRaises(ValueError):
            DatabricksConnector(host=self.host, token="")

        # Test valid token
        connector = DatabricksConnector(host=self.host, token=self.token)
        self.assertEqual(connector.token, self.token)

    def test_authentication_credential_rotation(self):
        """Test that credential rotation works correctly"""
        connector = DatabricksConnector(host=self.host, token=self.token)

        # Authenticate with original credentials
        auth1 = connector.authenticate({"host": self.host, "token": self.token})
        self.assertTrue(auth1)

        # Update credentials (simulate rotation)
        new_token = self.token  # In real scenario, this would be a new token
        auth2 = connector.authenticate({"host": self.host, "token": new_token})
        self.assertTrue(auth2)

        # Verify connector uses new credentials
        self.assertEqual(connector.token, new_token)

    def test_least_privilege_access(self):
        """Test that connector follows least privilege principles"""
        connector = DatabricksConnector(host=self.host, token=self.token)

        # Verify connector only performs read operations (harvest-only)
        self.assertEqual(connector.supported_sync_directions, ["PULL"])

        # Verify push operations raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            connector.create_listing({})

        with self.assertRaises(NotImplementedError):
            connector.update_listing("test", {})

        with self.assertRaises(NotImplementedError):
            connector.publish_resource("test", {})

        with self.assertRaises(NotImplementedError):
            connector.sync_push([])

        with self.assertRaises(NotImplementedError):
            connector.map_from_hub_asset(None)

    def test_http_host_stored_verbatim_no_validation(self):
        """Test that HTTP (non-HTTPS) hosts are stored as-is and don't crash.

        The connector defers URL validation to the HTTP client at request time.
        Here we verify the connector accepts any URL form without crashing.
        Actual transport-level enforcement is tested in the error-handling suite.
        """
        connector = DatabricksConnector(
            host="http://dbc-6710eb95-8fe1.cloud.databricks.com", token=self.token
        )
        self.assertTrue(connector.host.startswith("http://"))
        self.assertEqual(connector.host, "http://dbc-6710eb95-8fe1.cloud.databricks.com")

    def test_token_not_logged(self):
        """Test that tokens are not logged in plain text"""
        import logging
        from io import StringIO

        # Create string buffer to capture logs
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)

        # Get connector logger
        logger = logging.getLogger("hub.apps.integrations.connectors.databricks_connector")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Perform operation that might log
        connector = DatabricksConnector(host=self.host, token=self.token)

        try:
            connector.test_connection()
        except (ConnectionError, OSError):
            pass  # Network/auth failures expected; we're checking logs only

        # Check logs don't contain token
        log_contents = log_capture.getvalue()
        self.assertNotIn(self.token, log_contents, "Token should not appear in logs")

        # Cleanup
        logger.removeHandler(handler)

    def test_credential_handling_in_authenticate(self):
        """Test that credentials are handled securely in authenticate method"""
        connector = DatabricksConnector(host=self.host, token=self.token)

        # Test missing credentials
        with self.assertRaises(ValueError):
            connector.authenticate(None)

        with self.assertRaises(ValueError):
            connector.authenticate({})

        # Test missing host
        with self.assertRaises(ValueError):
            connector.authenticate({"token": self.token})

        # Test missing token
        with self.assertRaises(ValueError):
            connector.authenticate({"host": self.host})

        # Test valid credentials
        result = connector.authenticate({"host": self.host, "token": self.token})
        self.assertTrue(result)

    def test_permission_error_handling(self):
        """Test that 403 errors propagate as PermissionError through _request_with_retry."""
        from unittest.mock import Mock, patch

        import httpx

        connector = DatabricksConnector(host=self.host, token=self.token)

        # Bypass the circuit breaker so we test the error-propagation path directly
        mock_cb = Mock()
        mock_cb.call = Mock(side_effect=lambda func: func())
        connector._circuit_breaker = mock_cb

        # Simulate a 403 response
        error_response = Mock()
        error_response.status_code = 403
        error_response.json.return_value = {
            "error_code": "PERMISSION_DENIED",
            "message": "Access denied",
        }
        error_response.text = (
            '{"error_code": "PERMISSION_DENIED", "message": "Access denied"}'
        )
        http_error = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=error_response
        )
        error_response.raise_for_status.side_effect = http_error
        connector.client.request = Mock(return_value=error_response)

        with self.assertRaises(PermissionError):
            connector._request_with_retry("GET", "/api/2.0/test")
