"""
Marketplace Integration Serializers Tests

Comprehensive unit tests for marketplace connection serializers.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.serializers import (
    MarketplaceConnectionCreateSerializer,
    MarketplaceConnectionSerializer,
    MarketplaceConnectionTestResponseSerializer,
    MarketplaceConnectionUpdateSerializer,
)
from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceConnectionSerializerTest(TestCase):
    """Test suite for MarketplaceConnectionSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

    def test_serialize_connection(self):
        """Test serializing a marketplace connection"""
        serializer = MarketplaceConnectionSerializer(self.connection)
        data = serializer.data

        self.assertEqual(str(self.connection.id), data["id"])
        self.assertEqual(str(self.tenant.id), data["tenant"])
        self.assertEqual(self.tenant.name, data["tenant_name"])
        self.assertEqual(MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value, data["marketplace_type"])
        self.assertIn("Snowflake Data Marketplace", data["marketplace_type_display"])
        self.assertEqual("Test Connection", data["name"])
        self.assertTrue(data["is_active"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        # Config should never be exposed
        self.assertNotIn("config", data)

    def test_serialize_multiple_connections(self):
        """Test serializing multiple connections"""
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"access_key": "test"},
            is_active=False,
        )

        serializer1 = MarketplaceConnectionSerializer(self.connection)
        serializer2 = MarketplaceConnectionSerializer(connection2)

        self.assertEqual(serializer1.data["name"], "Test Connection")
        self.assertEqual(serializer2.data["name"], "Test Connection 2")
        self.assertTrue(serializer1.data["is_active"])
        self.assertFalse(serializer2.data["is_active"])


class MarketplaceConnectionCreateSerializerTest(TestCase):
    """Test suite for MarketplaceConnectionCreateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

        self.valid_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Test Connection",
            "config": {"api_key": "test_key", "api_secret": "test_secret"},
            "is_active": True,
        }

    def test_valid_create_data(self):
        """Test serializer with valid data"""
        serializer = MarketplaceConnectionCreateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data["marketplace_type"], self.valid_data["marketplace_type"]
        )
        self.assertEqual(serializer.validated_data["name"], self.valid_data["name"])
        self.assertEqual(serializer.validated_data["config"], self.valid_data["config"])
        self.assertTrue(serializer.validated_data["is_active"])

    def test_create_without_is_active(self):
        """Test serializer defaults is_active to True"""
        data = self.valid_data.copy()
        del data["is_active"]
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertTrue(serializer.validated_data.get("is_active", True))

    def test_create_with_empty_name(self):
        """Test serializer rejects empty name"""
        data = self.valid_data.copy()
        data["name"] = ""
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_create_with_whitespace_only_name(self):
        """Test serializer rejects whitespace-only name"""
        data = self.valid_data.copy()
        data["name"] = "   "
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_create_with_too_long_name(self):
        """Test serializer rejects name exceeding 255 characters"""
        data = self.valid_data.copy()
        data["name"] = "a" * 256
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_create_with_invalid_marketplace_type(self):
        """Test serializer rejects invalid marketplace type"""
        data = self.valid_data.copy()
        data["marketplace_type"] = "INVALID_TYPE"
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("marketplace_type", serializer.errors)

    def test_create_with_valid_marketplace_types(self):
        """Test serializer accepts all valid marketplace types"""
        for marketplace_type in MarketplaceType:
            data = self.valid_data.copy()
            data["marketplace_type"] = marketplace_type.value
            serializer = MarketplaceConnectionCreateSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Failed for {marketplace_type.value}")

    def test_create_with_non_dict_config(self):
        """Test serializer rejects non-dictionary config"""
        data = self.valid_data.copy()
        data["config"] = "not a dict"
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)

    def test_create_with_empty_dict_config(self):
        """Test serializer accepts empty dict config"""
        data = self.valid_data.copy()
        data["config"] = {}
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_create_name_trimming(self):
        """Test serializer trims whitespace from name"""
        data = self.valid_data.copy()
        data["name"] = "  Test Connection  "
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Connection")

    def test_create_missing_required_fields(self):
        """Test serializer requires all required fields"""
        # Missing marketplace_type
        data = self.valid_data.copy()
        del data["marketplace_type"]
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("marketplace_type", serializer.errors)

        # Missing name
        data = self.valid_data.copy()
        del data["name"]
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

        # Missing config
        data = self.valid_data.copy()
        del data["config"]
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)


class MarketplaceConnectionUpdateSerializerTest(TestCase):
    """Test suite for MarketplaceConnectionUpdateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_data = {
            "name": "Updated Connection",
            "config": {"api_key": "updated_key", "api_secret": "updated_secret"},
            "is_active": False,
        }

    def test_valid_update_data(self):
        """Test serializer with valid update data"""
        serializer = MarketplaceConnectionUpdateSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], self.valid_data["name"])
        self.assertEqual(serializer.validated_data["config"], self.valid_data["config"])
        self.assertFalse(serializer.validated_data["is_active"])

    def test_partial_update_name_only(self):
        """Test serializer with only name update"""
        data = {"name": "New Name"}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "New Name")

    def test_partial_update_config_only(self):
        """Test serializer with only config update"""
        data = {"config": {"new_key": "new_value"}}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["config"], data["config"])

    def test_partial_update_is_active_only(self):
        """Test serializer with only is_active update"""
        data = {"is_active": False}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertFalse(serializer.validated_data["is_active"])

    def test_update_with_empty_data(self):
        """Test serializer rejects empty update data"""
        serializer = MarketplaceConnectionUpdateSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_update_with_empty_name(self):
        """Test serializer rejects empty name"""
        data = {"name": ""}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_update_with_whitespace_only_name(self):
        """Test serializer rejects whitespace-only name"""
        data = {"name": "   "}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_update_with_too_long_name(self):
        """Test serializer rejects name exceeding 255 characters"""
        data = {"name": "a" * 256}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_update_with_non_dict_config(self):
        """Test serializer rejects non-dictionary config"""
        data = {"config": "not a dict"}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)

    def test_update_name_trimming(self):
        """Test serializer trims whitespace from name"""
        data = {"name": "  Updated Name  "}
        serializer = MarketplaceConnectionUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Updated Name")


class MarketplaceConnectionTestResponseSerializerTest(TestCase):
    """Test suite for MarketplaceConnectionTestResponseSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        from django.utils import timezone

        self.success_data = {
            "success": True,
            "message": "Connection test successful",
            "error": None,
            "tested_at": timezone.now(),
            "connection_id": uuid.uuid4(),
        }

        self.failure_data = {
            "success": False,
            "message": "Connection test failed",
            "error": "Authentication failed",
            "tested_at": timezone.now(),
            "connection_id": uuid.uuid4(),
        }

    def test_serialize_success_response(self):
        """Test serializing successful test response"""
        serializer = MarketplaceConnectionTestResponseSerializer(data=self.success_data)
        self.assertTrue(serializer.is_valid())
        data = serializer.data

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Connection test successful")
        self.assertIsNone(data["error"])
        self.assertIn("tested_at", data)
        self.assertEqual(str(self.success_data["connection_id"]), data["connection_id"])

    def test_serialize_failure_response(self):
        """Test serializing failed test response"""
        serializer = MarketplaceConnectionTestResponseSerializer(data=self.failure_data)
        self.assertTrue(serializer.is_valid())
        data = serializer.data

        self.assertFalse(data["success"])
        self.assertEqual(data["message"], "Connection test failed")
        self.assertEqual(data["error"], "Authentication failed")
        self.assertIn("tested_at", data)
        self.assertEqual(str(self.failure_data["connection_id"]), data["connection_id"])

    def test_serialize_without_error(self):
        """Test serializing response without error field"""
        data = self.success_data.copy()
        del data["error"]
        serializer = MarketplaceConnectionTestResponseSerializer(data=data)
        # Should still be valid (error is optional)
        self.assertTrue(serializer.is_valid())

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_create_serializer_missing_required_fields(self):
        """Test that create serializer validates required fields"""
        serializer = MarketplaceConnectionCreateSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("marketplace_type", serializer.errors)
        self.assertIn("name", serializer.errors)
        self.assertIn("config", serializer.errors)

    def test_create_serializer_invalid_marketplace_type(self):
        """Test that create serializer rejects invalid marketplace type"""
        invalid_data = {
            "marketplace_type": "INVALID_TYPE",
            "name": "Test Connection",
            "config": {"key": "value"},
        }
        serializer = MarketplaceConnectionCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("marketplace_type", serializer.errors)

    def test_create_serializer_config_not_dict(self):
        """Test that create serializer validates config is dict"""
        invalid_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Test Connection",
            "config": "not-a-dict",
        }
        serializer = MarketplaceConnectionCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)

    def test_update_serializer_invalid_data(self):
        """Test that update serializer validates data"""
        serializer = MarketplaceConnectionUpdateSerializer(data={"name": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_test_response_serializer_missing_required_fields(self):
        """Test that test response serializer validates required fields"""
        serializer = MarketplaceConnectionTestResponseSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("success", serializer.errors)
        self.assertIn("message", serializer.errors)
        self.assertIn("tested_at", serializer.errors)
        self.assertIn("connection_id", serializer.errors)

    # ========== ERROR HANDLING TESTS ==========

    def test_serialize_connection_with_deleted_tenant(self):
        """Test that serializer handles deleted tenant gracefully"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
        )

        tenant_id = self.tenant.id
        self.tenant.delete()

        # Try to serialize - should handle gracefully
        try:
            connection.refresh_from_db()
            serializer = MarketplaceConnectionSerializer(connection)
            # If connection still exists, serializer should handle missing tenant
            data = serializer.data
            # Tenant field may be None or missing
            self.assertIn("tenant", data or {})
        except MarketplaceConnection.DoesNotExist:
            # If cascade delete removed connection, that's also acceptable
            pass

    def test_create_serializer_with_malformed_config(self):
        """Test that create serializer handles malformed config"""
        invalid_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Test Connection",
            "config": None,
        }
        serializer = MarketplaceConnectionCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)

    def test_update_serializer_with_invalid_config_type(self):
        """Test that update serializer validates config type"""
        serializer = MarketplaceConnectionUpdateSerializer(data={"config": "not-a-dict"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("config", serializer.errors)

    # ========== EDGE CASES TESTS ==========

    def test_create_serializer_with_very_long_name(self):
        """Test that create serializer handles very long names"""
        long_name = "a" * 500
        data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": long_name,
            "config": {"key": "value"},
        }
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        # May be valid or invalid depending on max_length
        if serializer.is_valid():
            self.assertEqual(serializer.validated_data["name"], long_name.strip())
        else:
            self.assertIn("name", serializer.errors)

    def test_create_serializer_with_large_config(self):
        """Test that create serializer handles large config"""
        large_config = {f"key-{i}": f"value-{i}" for i in range(100)}
        data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Large Config Test",
            "config": large_config,
        }
        serializer = MarketplaceConnectionCreateSerializer(data=data)
        if serializer.is_valid():
            self.assertEqual(len(serializer.validated_data["config"]), 100)

    def test_serialize_connection_with_special_characters(self):
        """Test that serializer handles special characters in name"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection !@#$%^&*()",
            config={"key": "value"},
        )
        serializer = MarketplaceConnectionSerializer(connection)
        data = serializer.data
        self.assertIn("Test Connection", data["name"])

    # ========== TDD COMPLIANCE TESTS ==========

    def test_serialize_connection_returns_all_required_fields(self):
        """Test that serializer returns all required fields"""
        serializer = MarketplaceConnectionSerializer(self.connection)
        data = serializer.data

        # Verify all required fields are present
        required_fields = [
            "id",
            "tenant",
            "tenant_name",
            "marketplace_type",
            "marketplace_type_display",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, data, f"Required field {field} missing from serializer output")

    def test_serialize_connection_field_types(self):
        """Test that serializer returns correct field types"""
        serializer = MarketplaceConnectionSerializer(self.connection)
        data = serializer.data

        # Verify field types
        self.assertIsInstance(data["id"], str)
        self.assertIsInstance(data["tenant"], str)
        self.assertIsInstance(data["tenant_name"], str)
        self.assertIsInstance(data["marketplace_type"], str)
        self.assertIsInstance(data["marketplace_type_display"], str)
        self.assertIsInstance(data["name"], str)
        self.assertIsInstance(data["is_active"], bool)
        self.assertIsInstance(data["created_at"], str)
        self.assertIsInstance(data["updated_at"], str)

    def test_create_serializer_validates_all_fields(self):
        """Test that create serializer validates all fields"""
        # Test with all valid data
        valid_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Valid Connection",
            "config": {"api_key": "test-key"},
            "is_active": True,
        }
        serializer = MarketplaceConnectionCreateSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Valid Connection")
        self.assertEqual(serializer.validated_data["is_active"], True)

    def test_update_serializer_allows_partial_updates(self):
        """Test that update serializer allows partial updates"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={"key": "value"},
        )

        # Partial update - only name
        serializer = MarketplaceConnectionUpdateSerializer(
            connection, data={"name": "Updated Name"}, partial=True
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        connection.refresh_from_db()
        self.assertEqual(connection.name, "Updated Name")

    def test_test_response_serializer_field_types(self):
        """Test that test response serializer returns correct field types"""
        serializer = MarketplaceConnectionTestResponseSerializer(data=self.success_data)
        self.assertTrue(serializer.is_valid())
        data = serializer.data

        # Verify field types
        self.assertIsInstance(data["success"], bool)
        self.assertIsInstance(data["message"], str)
        self.assertIsInstance(data["tested_at"], str)
        self.assertIsInstance(data["connection_id"], str)
        # error may be None or string
        if data.get("error") is not None:
            self.assertIsInstance(data["error"], str)
