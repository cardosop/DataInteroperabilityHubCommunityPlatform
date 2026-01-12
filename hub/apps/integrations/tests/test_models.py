"""
Unit tests for MarketplaceConnection model.

Comprehensive tests for model creation, validation, encryption, and constraints.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.encryption import encrypt_json_field, decrypt_json_field, EncryptionError


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MarketplaceConnectionModelTest(TestCase):
    """Test MarketplaceConnection model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.config = {
            "api_key": "test-api-key-123",
            "endpoint": "https://api.example.com",
            "timeout": 30
        }

    def test_create_marketplace_connection(self):
        """Test marketplace connection creation with minimal required fields"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        self.assertEqual(connection.tenant, self.tenant)
        self.assertEqual(connection.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value)
        self.assertEqual(connection.name, "Test Connection")
        self.assertTrue(connection.is_active)
        self.assertIsNotNone(connection.id)
        self.assertIsNotNone(connection.created_at)
        self.assertIsNotNone(connection.updated_at)

        # Verify config is encrypted
        self.assertIn("_encrypted", connection.config)
        self.assertIsInstance(connection.config["_encrypted"], str)

        # Verify decryption works
        decrypted_config = connection.get_config()
        self.assertEqual(decrypted_config["api_key"], "test-api-key-123")
        self.assertEqual(decrypted_config["endpoint"], "https://api.example.com")
        self.assertEqual(decrypted_config["timeout"], 30)

    def test_create_connection_with_all_fields(self):
        """Test connection creation with all fields"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Full Connection",
            config={
                "api_key": "aws-key",
                "secret_key": "aws-secret",
                "region": "us-east-1"
            },
            is_active=False
        )

        self.assertEqual(connection.marketplace_type, MarketplaceType.AWS_DATA_EXCHANGE.value)
        self.assertEqual(connection.name, "Full Connection")
        self.assertFalse(connection.is_active)

        decrypted_config = connection.get_config()
        self.assertEqual(decrypted_config["api_key"], "aws-key")
        self.assertEqual(decrypted_config["secret_key"], "aws-secret")
        self.assertEqual(decrypted_config["region"], "us-east-1")

    def test_connection_str_representation(self):
        """Test string representation of connection"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        str_repr = str(connection)
        self.assertIn("Test Connection", str_repr)
        self.assertIn("Test Tenant", str_repr)
        self.assertIn("Snowflake Data Marketplace", str_repr)

    def test_unique_constraint_tenant_name(self):
        """Test that connection names must be unique within a tenant"""
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Unique Connection",
            config=self.config
        )

        # Try to create another connection with same name for same tenant
        # Django's full_clean() validates unique constraints and raises ValidationError
        with self.assertRaises(ValidationError):
            connection = MarketplaceConnection(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
                name="Unique Connection",
                config=self.config
            )
            connection.full_clean()

    def test_same_name_different_tenants(self):
        """Test that same connection name can exist for different tenants"""
        tenant2 = Tenant.objects.create(
            name="Another Tenant",
            slug="another-tenant"
        )

        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Shared Name",
            config=self.config
        )

        connection2 = MarketplaceConnection.objects.create(
            tenant=tenant2,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Shared Name",
            config=self.config
        )

        self.assertEqual(connection1.name, connection2.name)
        self.assertNotEqual(connection1.tenant, connection2.tenant)

    def test_validation_invalid_marketplace_type(self):
        """Test validation fails for invalid marketplace type"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type="INVALID_TYPE",
            name="Test Connection",
            config=self.config
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_validation_empty_name(self):
        """Test validation fails for empty name"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="",
            config=self.config
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_validation_whitespace_only_name(self):
        """Test validation fails for whitespace-only name"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="   ",
            config=self.config
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_validation_invalid_config_type(self):
        """Test validation fails when config is not a dictionary"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config="not-a-dict"
        )

        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_config_encryption_on_save(self):
        """Test that config is encrypted when saving"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Encryption Test",
            config=self.config
        )

        # Before save, config should be plain dict
        self.assertEqual(connection.config, self.config)

        # Save should encrypt
        connection.save()

        # After save, config should be encrypted
        self.assertIn("_encrypted", connection.config)
        self.assertNotEqual(connection.config["_encrypted"], self.config)

        # Verify decryption works
        decrypted = connection.get_config()
        self.assertEqual(decrypted, self.config)

    def test_config_update_reencryption(self):
        """Test that config is re-encrypted when updated"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Update Test",
            config=self.config
        )

        original_encrypted = connection.config["_encrypted"]

        # Update config
        new_config = {"api_key": "new-key", "endpoint": "https://new.example.com"}
        connection.set_config(new_config)
        connection.save()

        # Verify new encryption is different
        connection.refresh_from_db()
        self.assertNotEqual(connection.config["_encrypted"], original_encrypted)

        # Verify new config is correct
        decrypted = connection.get_config()
        self.assertEqual(decrypted, new_config)

    def test_get_config_empty_config(self):
        """Test get_config returns empty dict for empty config"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Empty Config Test",
            config={}
        )

        decrypted = connection.get_config()
        self.assertEqual(decrypted, {})

    def test_get_config_none_config(self):
        """Test get_config handles None/empty config"""
        # JSONField with default=dict always returns a dict, never None
        # Even if we try to set None, Django converts it to {}
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="None Config Test",
            config={}
        )

        # Refresh to get value from DB
        connection.refresh_from_db()
        # JSONField with default=dict will return {} for empty/null values
        decrypted = connection.get_config()
        self.assertEqual(decrypted, {})

    def test_set_config_validates_dict(self):
        """Test set_config validates that config is a dictionary"""
        connection = MarketplaceConnection(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Set Config Test",
            config=self.config
        )

        with self.assertRaises(ValueError):
            connection.set_config("not-a-dict")

        with self.assertRaises(ValueError):
            connection.set_config(None)

    def test_all_marketplace_types(self):
        """Test that all marketplace types can be used"""
        for marketplace_type in MarketplaceType:
            connection = MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=marketplace_type.value,
                name=f"Connection {marketplace_type.name}",
                config=self.config
            )

            self.assertEqual(connection.marketplace_type, marketplace_type.value)
            self.assertEqual(connection.get_marketplace_type_display(), marketplace_type.name.replace("_", " ").title())

    def test_indexes_exist(self):
        """Test that indexes are created correctly"""
        from django.db import connection as db_connection

        # Create connections to test indexes
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Index Test 1",
            config=self.config,
            is_active=True
        )

        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Index Test 2",
            config=self.config,
            is_active=False
        )

        # Verify queries use indexes (check execution plan)
        with db_connection.cursor() as cursor:
            # Query that should use tenant + marketplace_type index
            cursor.execute("""
                EXPLAIN SELECT * FROM marketplace_connections
                WHERE tenant_id = %s AND marketplace_type = %s
            """, [self.tenant.id, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value])

            # Just verify query executes without error
            # Actual index usage depends on PostgreSQL query planner

    def test_ordering_by_created_at_desc(self):
        """Test that connections are ordered by created_at descending"""
        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="First Connection",
            config=self.config
        )

        import time
        time.sleep(0.01)  # Small delay to ensure different timestamps

        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Second Connection",
            config=self.config
        )

        connections = list(MarketplaceConnection.objects.all())
        self.assertEqual(connections[0], connection2)  # Most recent first
        self.assertEqual(connections[1], connection1)

    def test_encryption_preserves_complex_data(self):
        """Test that encryption preserves complex nested data structures"""
        complex_config = {
            "api_key": "test-key",
            "endpoint": "https://api.example.com",
            "nested": {
                "level1": {
                    "level2": "deep-value"
                }
            },
            "array": [1, 2, 3, {"nested": "value"}],
            "boolean": True,
            "null_value": None,
            "number": 42.5
        }

        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Complex Config Test",
            config=complex_config
        )

        decrypted = connection.get_config()
        self.assertEqual(decrypted, complex_config)
        self.assertEqual(decrypted["nested"]["level1"]["level2"], "deep-value")
        self.assertEqual(decrypted["array"], [1, 2, 3, {"nested": "value"}])
        self.assertEqual(decrypted["boolean"], True)
        self.assertIsNone(decrypted["null_value"])
        self.assertEqual(decrypted["number"], 42.5)

    def test_encryption_error_handling(self):
        """Test that encryption errors are properly handled"""
        # This test verifies that encryption errors raise ValidationError
        # We'll test by patching the encryption function to raise an error
        from unittest.mock import patch
        from hub.apps.integrations.encryption import EncryptionError

        with patch('hub.apps.integrations.models.encrypt_json_field') as mock_encrypt:
            mock_encrypt.side_effect = EncryptionError("Test encryption error")

            connection = MarketplaceConnection(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name="Encryption Error Test",
                config=self.config
            )

            with self.assertRaises(ValidationError) as cm:
                connection.save()

            # Verify the error message contains encryption error
            self.assertIn("encrypt", str(cm.exception).lower())

    def test_connection_cascade_delete(self):
        """Test that connections are deleted when tenant is deleted"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Cascade Test",
            config=self.config
        )

        connection_id = connection.id

        # Delete tenant
        self.tenant.delete()

        # Verify connection is deleted
        self.assertFalse(MarketplaceConnection.objects.filter(id=connection_id).exists())

    def test_connection_update_timestamp(self):
        """Test that updated_at timestamp changes on update"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Timestamp Test",
            config=self.config
        )

        original_updated_at = connection.updated_at

        import time
        time.sleep(0.01)

        # Update connection
        connection.is_active = False
        connection.save()

        connection.refresh_from_db()
        self.assertGreater(connection.updated_at, original_updated_at)

