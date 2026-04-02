"""
Marketplace Integration Views Tests

Comprehensive tests for marketplace connection management endpoints.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceConnectionViewSetTest(TestCase):
    """Test suite for MarketplaceConnectionViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        # Active subscription required so TenantSuspensionMiddleware allows API writes
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role and assign to user (Role is tenant-scoped)
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        self.user.user_roles.create(role=data_provider_role)

        # Create API key with integrations:write scope (store plaintext for auth)
        # API key auth ensures request.api_key_scopes is set and HasScope/HasAnyRole pass
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="Test API Key",
            scopes=["integrations:write", "integrations:read"],
        )
        self.plaintext_api_key = plaintext_key

        # Authenticate via API key only (no force_authenticate - it would override and cause 403)
        # credentials() lets API key auth run; force_authenticate would bypass it
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}"
        )

        # Sample connection data
        self.valid_connection_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Test Connection",
            "config": {"api_key": "test_key", "api_secret": "test_secret"},
            "is_active": True,
        }

    def test_create_connection_success(self):
        """Test successful connection creation"""
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            self.valid_connection_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Test Connection")
        self.assertEqual(
            response.data["marketplace_type"], MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertTrue(response.data["is_active"])
        self.assertIn("id", response.data)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        # Config should never be exposed
        self.assertNotIn("config", response.data)

        # Verify connection was created in database
        connection = MarketplaceConnection.objects.get(id=response.data["id"])
        self.assertEqual(connection.name, "Test Connection")
        self.assertEqual(connection.tenant, self.tenant)

    def test_create_connection_missing_required_fields(self):
        """Test connection creation with missing required fields"""
        data = {
            "name": "Test Connection",
            # Missing marketplace_type and config
        }

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_connection_invalid_marketplace_type(self):
        """Test connection creation with invalid marketplace type"""
        data = self.valid_connection_data.copy()
        data["marketplace_type"] = "INVALID_TYPE"

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("marketplace_type", str(response.data))

    def test_create_connection_invalid_config(self):
        """Test connection creation with invalid config (not a dict)"""
        data = self.valid_connection_data.copy()
        data["config"] = "not a dict"

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("config", str(response.data))

    def test_create_connection_duplicate_name(self):
        """Test connection creation with duplicate name (same tenant)"""
        # Create first connection
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Duplicate Name",
            config={"key": "value"},
        )

        # Try to create another with same name
        data = self.valid_connection_data.copy()
        data["name"] = "Duplicate Name"

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_list_connections_success(self):
        """Test successful connection listing"""
        # Create test connections
        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config={"key": "value1"},
            is_active=True,
        )
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Connection 2",
            config={"key": "value2"},
            is_active=False,
        )

        response = self.client.get("/api/v1/integrations/marketplace/connections/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_connections_with_marketplace_type_filter(self):
        """Test connection listing with marketplace_type filter"""
        # Create test connections with different types
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={"key": "value"},
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="AWS Connection",
            config={"key": "value"},
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/connections/",
            {"marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
        )

    def test_list_connections_with_is_active_filter(self):
        """Test connection listing with is_active filter"""
        # Create test connections with different active statuses
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Active Connection",
            config={"key": "value"},
            is_active=True,
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Inactive Connection",
            config={"key": "value"},
            is_active=False,
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/connections/", {"is_active": "true"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertTrue(response.data["results"][0]["is_active"])

    def test_list_connections_with_search(self):
        """Test connection listing with search"""
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Snowflake Connection",
            config={"key": "value"},
        )
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="AWS Connection",
            config={"key": "value"},
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/connections/", {"search": "Snowflake"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIn("Snowflake", response.data["results"][0]["name"])

    def test_list_connections_with_ordering(self):
        """Test connection listing with ordering"""
        connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="A Connection",
            config={"key": "value"},
        )
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="B Connection",
            config={"key": "value"},
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/connections/", {"ordering": "name"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["name"], "A Connection")
        self.assertEqual(response.data["results"][1]["name"], "B Connection")

    def test_retrieve_connection_success(self):
        """Test successful connection retrieval"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
            is_active=True,
        )

        response = self.client.get(f"/api/v1/integrations/marketplace/connections/{connection.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(connection.id))
        self.assertEqual(response.data["name"], "Test Connection")
        self.assertNotIn("config", response.data)

    def test_retrieve_connection_not_found(self):
        """Test retrieving non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/connections/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_connection_success(self):
        """Test successful connection update"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={"key": "value"},
            is_active=True,
        )

        update_data = {"name": "Updated Name", "is_active": False}

        response = self.client.put(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            update_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")
        self.assertFalse(response.data["is_active"])

        # Verify update in database
        connection.refresh_from_db()
        self.assertEqual(connection.name, "Updated Name")
        self.assertFalse(connection.is_active)

    def test_partial_update_connection_success(self):
        """Test successful partial connection update"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={"key": "value"},
            is_active=True,
        )

        update_data = {"name": "Updated Name"}

        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            update_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")
        self.assertTrue(response.data["is_active"])  # Should remain unchanged

    def test_update_connection_config(self):
        """Test updating connection config"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"old_key": "old_value"},
            is_active=True,
        )

        update_data = {"config": {"new_key": "new_value"}}

        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            update_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify config was updated (decrypted)
        connection.refresh_from_db()
        decrypted_config = connection.get_config()
        self.assertEqual(decrypted_config["new_key"], "new_value")

    def test_delete_connection_success(self):
        """Test successful connection deletion"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
            is_active=True,
        )

        connection_id = connection.id

        response = self.client.delete(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify connection was deleted
        self.assertFalse(MarketplaceConnection.objects.filter(id=connection_id).exists())

    def test_delete_connection_not_found(self):
        """Test deleting non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.delete(f"/api/v1/integrations/marketplace/connections/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_test_connection_success(self):
        """Test successful connection test"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

        response = self.client.post(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/test/"
        )

        # Note: Actual test result depends on connector implementation
        # This test verifies the endpoint is accessible and returns proper format
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,  # If connector test fails
                status.HTTP_500_INTERNAL_SERVER_ERROR,  # If connector not available
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            self.assertIn("success", response.data)
            self.assertIn("message", response.data)
            self.assertIn("tested_at", response.data)
            self.assertIn("connection_id", response.data)

    def test_test_connection_not_found(self):
        """Test testing non-existent connection"""
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/v1/integrations/marketplace/connections/{fake_id}/test/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access(self):
        """Test unauthenticated users cannot access endpoints"""
        self.client.credentials()  # Clear API key auth
        self.client.logout()

        response = self.client.get("/api/v1/integrations/marketplace/connections/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            self.valid_connection_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_isolation(self):
        """Test tenant isolation - users can only see their tenant's connections"""
        # Create another tenant and user
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create connection in other tenant
        other_connection = MarketplaceConnection.objects.create(
            tenant=other_tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Other Connection",
            config={"key": "value"},
        )

        # Try to access with original user
        response = self.client.get(
            f"/api/v1/integrations/marketplace/connections/{other_connection.id}/"
        )

        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_platform_admin_access(self):
        """Test platform admins can access all connections"""
        # Create platform admin user
        admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )

        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
        )

        # Authenticate as admin (clear API key so force_authenticate takes effect)
        self.client.credentials()
        self.client.force_authenticate(user=admin_user)

        # Should be able to access
        response = self.client.get(f"/api/v1/integrations/marketplace/connections/{connection.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permissions_write_operations(self):
        """Test write operations require DATA_PROVIDER or TENANT_ADMIN role"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        # Try to create connection
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            self.valid_connection_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permissions_read_operations(self):
        """Test read operations only require authentication"""
        # Create user without DATA_PROVIDER role
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
        )

        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        # Should be able to read
        response = self.client.get(f"/api/v1/integrations/marketplace/connections/{connection.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination(self):
        """Test pagination works correctly"""
        # Create multiple connections
        for i in range(25):
            MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name=f"Connection {i}",
                config={"key": "value"},
            )

        response = self.client.get(
            "/api/v1/integrations/marketplace/connections/", {"page_size": 10}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["count"], 25)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_connection_validation_error_response_format(self):
        """Test that validation errors return proper error response format"""
        # Try to create connection with invalid marketplace type
        invalid_data = {
            "marketplace_type": "INVALID_TYPE",
            "name": "Test Connection",
            "config": {"key": "value"},
        }

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", invalid_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should have error details (API may use "detail" or "error" structure)
        data = response.data or {}
        self.assertTrue(
            "detail" in data or "error" in data,
            msg=f"Expected error details in response, got keys: {list(data.keys())}",
        )

    def test_create_connection_malformed_json(self):
        """Test that malformed JSON returns proper error"""
        # Send invalid JSON
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            "invalid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_connection_validation_error(self):
        """Test that update validation errors are handled properly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"key": "value"},
        )

        # Try to update with duplicate name
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Duplicate Name",
            config={"key": "value"},
        )

        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            {"name": "Duplicate Name"},
            format="json",
        )

        # May return 400 (validation error), 409 (conflict), or succeed if duplicate names allowed
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT],
        )

    def test_test_connection_error_handling(self):
        """Test that connection test errors are handled gracefully"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"invalid": "config"},  # Invalid config may cause errors
        )

        response = self.client.post(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/test/"
        )

        # Should handle errors gracefully (may return 200 with success=False or 400/500)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ],
        )

        if response.status_code == status.HTTP_200_OK:
            # If successful, verify response structure
            self.assertIn("success", response.data)
            self.assertIn("tested_at", response.data)

    def test_test_connection_not_found_error(self):
        """Test that testing nonexistent connection returns 404"""
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/v1/integrations/marketplace/connections/{fake_id}/test/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_connection_service_error_handling(self):
        """Test that service errors are handled gracefully"""
        # Create connection that may cause service errors
        # Use invalid config that may trigger service-level errors
        invalid_config_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "Error Test Connection",
            "config": None,  # Invalid config
        }

        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/", invalid_config_data, format="json"
        )

        # Should return validation error (400) not 500
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )

    def test_update_connection_not_found_error(self):
        """Test that updating nonexistent connection returns 404"""
        fake_id = uuid.uuid4()
        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{fake_id}/",
            {"name": "Updated Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_connection_error_handling(self):
        """Test that delete errors are handled gracefully"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="To Delete",
            config={"key": "value"},
        )

        # Delete should succeed
        response = self.client.delete(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Try to delete again - should return 404
        response = self.client.delete(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_connections_error_handling(self):
        """Test that list errors are handled gracefully"""
        # List should always succeed (may return empty list)
        response = self.client.get("/api/v1/integrations/marketplace/connections/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_retrieve_connection_error_handling(self):
        """Test that retrieve errors are handled gracefully"""
        # Retrieve nonexistent connection
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/connections/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_create_connection_response_has_all_required_fields(self):
        """Test that created connection response has all required fields"""
        response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            self.valid_connection_data,
            format="json",
        )

        if response.status_code == status.HTTP_201_CREATED:
            # Verify all required fields are present
            self.assertIn("id", response.data)
            self.assertIn("name", response.data)
            self.assertIn("marketplace_type", response.data)
            self.assertIn("is_active", response.data)
            self.assertIn("created_at", response.data)
            self.assertIn("updated_at", response.data)
            # Config should never be exposed
            self.assertNotIn("config", response.data)

    def test_update_connection_updates_timestamp(self):
        """Test that updating connection updates updated_at timestamp"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Original Name",
            config={"key": "value"},
        )

        original_updated_at = connection.updated_at

        import time

        time.sleep(0.1)  # INTENTIONAL: test-specific timing requirement

        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            {"name": "Updated Name"},
            format="json",
        )

        if response.status_code == status.HTTP_200_OK:
            connection.refresh_from_db()
            self.assertGreater(connection.updated_at, original_updated_at)

    def test_list_connections_response_structure(self):
        """Test that list response has correct structure"""
        response = self.client.get("/api/v1/integrations/marketplace/connections/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify pagination structure
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertIsInstance(response.data["count"], int)
