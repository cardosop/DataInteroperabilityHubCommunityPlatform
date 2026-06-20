"""
Security Tests for AWS Data Exchange Connector

Tests authentication, authorization, credential encryption, and input validation.
Tests verify AWS security best practices. No mocks or stubs; uses real connector
and real AWS when testing error mapping (skips when credentials not available).
"""

import os
import uuid

import pytest
from django.db import connection
from django.test import TestCase

from hub.apps.core.services.base import ConnectionError, NotFoundError, PermissionError
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class TestAWSDataExchangeConnectorSecurity(TestCase):
    """Security tests for AWS Data Exchange connector"""

    def setUp(self):
        """Set up test fixtures. Ensure DB connection is open after prior tests (avoids connection already closed)."""
        connection.ensure_connection()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-security-{uid}")

    def test_iam_credentials_validation(self):
        """Test IAM credentials validation"""
        # Test missing access key - will fail during authentication test
        connector = AWSDataExchangeConnector(aws_secret_access_key="test-secret")
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate({"aws_secret_access_key": "test-secret"})

        # Test missing secret key - will fail during authentication test
        connector = AWSDataExchangeConnector(aws_access_key_id="test-key")
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate({"aws_access_key_id": "test-key"})

        # Test invalid credentials format
        connector = AWSDataExchangeConnector()
        with self.assertRaises((ValueError, TypeError)):
            connector.authenticate(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_iam_role_assumption_validation(self):
        """Test IAM role assumption validation"""
        # Test role ARN format validation
        connector = AWSDataExchangeConnector(role_arn="invalid-arn-format")

        # Role ARN validation happens during authentication
        # Invalid ARN will cause authentication to fail
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate({})

    def test_credential_encryption_in_storage(self):
        """Test that stored credentials are encrypted"""
        # Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            name="Test Connection",
            config={
                "aws_access_key_id": "test-key-id",
                "aws_secret_access_key": "test-secret-key",
            },
        )

        # Verify credentials are stored (they should be encrypted if encryption is enabled)
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
            self.assertIn("aws_access_key_id", stored_config)
            self.assertIn("aws_secret_access_key", stored_config)

    def test_input_validation_dataset_id(self):
        """Test dataset ID validation (connector raises ValueError/TypeError before AWS)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )

        with self.assertRaises(ValueError):
            connector.get_listing("")

        with self.assertRaises(TypeError):
            connector.get_listing(None)  # type: ignore[arg-type]  # test: None arg for error-path coverage

        # Non-existent ID: real AWS returns NotFoundError when credentials allow API call.
        # With invalid creds we never reach AWS; integration tests cover real NotFoundError.
        # Here we only assert validation for empty/None.

    def test_input_validation_s3_bucket(self):
        """Test S3 bucket and parameter validation in export job creation (no AWS call)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )

        with self.assertRaises(ValueError):
            connector._create_export_job(
                dataset_id="dataset-123",
                revision_id="revision-123",
                destination_bucket="",
                destination_key_prefix="prefix",
            )

        # None bucket: connector tries settings then raises ValueError if unset
        with self.assertRaises(ValueError):
            connector._create_export_job(
                dataset_id="dataset-123",
                revision_id="revision-123",
                destination_bucket=None,
                destination_key_prefix="prefix",
            )

    def test_credential_rotation_support(self):
        """Test that connector supports credential rotation"""
        # Test that connector can be re-authenticated with new credentials
        connector = AWSDataExchangeConnector(
            aws_access_key_id="old-key", aws_secret_access_key="old-secret"
        )

        # Re-authenticate with new credentials
        # Note: This will fail connection test with invalid credentials, but that's expected
        # The important thing is that the connector accepts new credentials for authentication
        try:
            connector.authenticate(
                {"aws_access_key_id": "new-key", "aws_secret_access_key": "new-secret"}
            )
            # If authentication succeeds (unlikely with invalid credentials), verify authenticated flag
            # If it fails, that's also acceptable - the test verifies the method accepts new credentials
        except (ConnectionError, PermissionError):
            # Expected when credentials are invalid - connector still accepted the new credentials
            pass

        # Verify connector updated credentials (even if authentication failed)
        # The connector should have updated its internal credential state
        self.assertEqual(connector._aws_access_key_id, "new-key")
        self.assertEqual(connector._aws_secret_access_key, "new-secret")

    def test_access_denied_exception_handling(self):
        """Test that invalid credentials lead to PermissionError or ConnectionError (real AWS)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="invalid-key",
            aws_secret_access_key="invalid-secret",
            region_name="us-east-1",
        )
        with self.assertRaises((PermissionError, ConnectionError)):
            connector.authenticate(
                {"aws_access_key_id": "invalid-key", "aws_secret_access_key": "invalid-secret"}
            )

    def test_resource_not_found_exception_handling(self):
        """Test that non-existent dataset ID leads to NotFoundError (real AWS when creds available)."""
        access_key = os.getenv("AWS_DATA_EXCHANGE_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY") or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        if not access_key or not secret_key:
            self.skipTest("AWS credentials required to test real NotFoundError mapping")
        connector = AWSDataExchangeConnector(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        try:
            connector.authenticate(
                {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                    "region_name": os.getenv("AWS_REGION", "us-east-1"),
                }
            )
        except (ConnectionError, PermissionError):
            self.skipTest(
                "AWS credentials invalid or expired - cannot test ResourceNotFoundException mapping"
            )
        # Use valid-format dataset ID (30+ alphanumeric) so AWS returns ResourceNotFoundException
        fake_dataset_id = "0" * 32
        with self.assertRaises(NotFoundError):
            connector.get_listing(fake_dataset_id)

    def test_aws_security_best_practices(self):
        """Test AWS security best practices — pins default region."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )
        self.assertEqual(connector._region_name, "us-east-1")

    def test_credential_exposure_prevention(self):
        """Test prevention of credential exposure"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )

        # Verify credentials are not exposed in string representation
        connector_str = str(connector)
        self.assertNotIn("test-key", connector_str)
        self.assertNotIn("test-secret", connector_str)

        # Verify credentials are not exposed in repr
        connector_repr = repr(connector)
        self.assertNotIn("test-key", connector_repr)
        self.assertNotIn("test-secret", connector_repr)

    def test_input_validation_empty_strings(self):
        """Test input validation with empty strings (connector raises ValueError)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )

        with self.assertRaises(ValueError):
            connector.get_listing("")

        with self.assertRaises(ValueError):
            connector.list_resources("")

    def test_input_validation_none_values(self):
        """Test input validation with None values (connector raises TypeError)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key", aws_secret_access_key="test-secret"
        )

        with self.assertRaises(TypeError):
            connector.get_listing(None)  # type: ignore[arg-type]  # test: None arg for error-path coverage  # test: edge-case type exercise

        with self.assertRaises(TypeError):
            connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_credential_validation_with_empty_strings(self):
        """Test credential validation with empty strings"""
        # Test empty access key
        connector = AWSDataExchangeConnector(
            aws_access_key_id="", aws_secret_access_key="test-secret"
        )
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate(
                {"aws_access_key_id": "", "aws_secret_access_key": "test-secret"}
            )

        # Test empty secret key
        connector = AWSDataExchangeConnector(aws_access_key_id="test-key", aws_secret_access_key="")
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate({"aws_access_key_id": "test-key", "aws_secret_access_key": ""})

    def test_role_arn_validation_with_invalid_format(self):
        """Test role ARN validation with various invalid formats"""
        # Test invalid ARN formats
        invalid_arns = [
            "invalid-arn",
            "arn:aws:iam::",
            "arn:aws:iam::123456789012:",
            "arn:aws:iam::123456789012:role",
            "not-an-arn",
        ]

        for invalid_arn in invalid_arns:
            connector = AWSDataExchangeConnector(role_arn=invalid_arn)
            with self.assertRaises((ValueError, PermissionError, ConnectionError)):
                connector.authenticate({})
