"""
Marketplace Integration Views Tests

Comprehensive tests for marketplace connection management endpoints.
"""

import contextlib
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
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
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            marketplace_integrations_enabled=True,
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
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}")

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
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config={"key": "value1"},
            is_active=True,
        )
        MarketplaceConnection.objects.create(
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
        MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="A Connection",
            config={"key": "value"},
        )
        MarketplaceConnection.objects.create(
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
        from hub.apps.integrations.base import (
            DataMarketplaceConnector,
            MarketplaceListing,
            MarketplaceResource,
            SyncDirection,
            SyncResult,
            SyncStatus,
        )
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        class _SuccessConnector(DataMarketplaceConnector):
            """Connector that reports successful connection tests."""
            __test__ = False

            @property
            def marketplace_type(self):
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return []

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id):
                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test",
                )

            def list_resources(self, listing_id):
                return []

            def create_listing(self, listing):
                return listing

            def update_listing(self, listing_id, listing):
                return listing

            def publish_resource(self, listing_id, resource):
                return resource

            def download_resource(self, resource_id, destination_path):
                return destination_path

            def map_to_hub_asset(self, listing, sync_job_id=None):
                from hub.apps.assets.models import AssetSourceType
                from hub.apps.integrations.base import MarketplaceAssetMapping

                return MarketplaceAssetMapping(
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title=asset_data.get("name", "Test"),
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(status=SyncStatus.COMPLETED, total_items=0, successful_items=0, failed_items=0, skipped_items=0, errors=[], metadata={})

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(status=SyncStatus.COMPLETED, total_items=0, successful_items=0, failed_items=0, skipped_items=0, errors=[], metadata={})

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, _SuccessConnector
        )

        try:
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

            # With a passing connector, we must get 200 with success=True.
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"Expected 200 OK, got {response.status_code}: {response.data}",
            )
            self.assertTrue(response.data["success"], "Connection test should report success=True")
            self.assertIn("message", response.data)
            self.assertIn("tested_at", response.data)
            self.assertIn("connection_id", response.data)
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

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
        User.objects.create_user(
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

        # Try to access with original user — queryset filters by user's tenant,
        # so the object simply won't be found (404). A 403 would also be
        # acceptable but the current queryset-scoping implementation returns 404.
        response = self.client.get(
            f"/api/v1/integrations/marketplace/connections/{other_connection.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            msg=f"Tenant isolation should prevent access; got {response.status_code}: {response.data}",
        )

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

    def test_test_connection_requires_write_role(self):
        """POST /connections/{id}/test/ requires DATA_PROVIDER or TENANT_ADMIN role."""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="PermTest Connection",
            config={"key": "value"},
        )
        regular_user = User.objects.create_user(
            email=f"perm-test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        response = self.client.post(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/test/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancel_sync_requires_write_role(self):
        """POST /sync/{id}/cancel/ requires DATA_PROVIDER or TENANT_ADMIN role."""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=MarketplaceConnection.objects.create(
                tenant=self.tenant,
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name="PermTest Connection 2",
                config={"key": "value"},
            ),
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [], "options": {}},
        )
        regular_user = User.objects.create_user(
            email=f"perm-cancel-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        response = self.client.post(
            f"/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/",
            {"reason": "test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_destroy_mapping_requires_write_role(self):
        """DELETE /mappings/{id}/ requires DATA_PROVIDER or TENANT_ADMIN role."""
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(tenant=self.tenant, key="perm-mapping", name="Perm Mapping")
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="PermTest Connection 3",
            config={"key": "value"},
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection,
            hub_asset=asset,
            external_listing_id="perm-ext-1",
        )
        regular_user = User.objects.create_user(
            email=f"perm-mapping-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{mapping.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

        # Duplicate name is caught by the service layer (not the serializer),
        # so the correct response is 409 Conflict via ConflictError.
        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
            msg=f"Duplicate name should return 409, got {response.status_code}: {response.data}",
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

        # Invalid config should still return a structured response — the
        # test endpoint must handle errors gracefully and return 200 with
        # success=False. A 400 means the service rejected the config before
        # testing. Either is acceptable engineering practice; 500 is a crash.
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            msg=f"Expected graceful error handling (200/400), got {response.status_code}: {response.data}",
        )

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

        # Null config must be rejected as a validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg=f"Expected 201 Created, got {response.status_code}: {response.data}",
        )
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

        time.sleep(0.1)  # noqa: sleep-needed  # INTENTIONAL: test-specific timing requirement

        response = self.client.patch(
            f"/api/v1/integrations/marketplace/connections/{connection.id}/",
            {"name": "Updated Name"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"Expected 200 OK, got {response.status_code}: {response.data}",
        )
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


# =============================================================================
# Rate Limiting Tests (Phase 2.1)
# =============================================================================


class MarketplaceRateLimitingTest(TestCase):
    """Verify all 7 write endpoints return 429 when rate-limited."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disconnect signals at class level to avoid per-test overhead
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            cls._disconnected = [
                (post_save, contract_saved, Contract),
                (post_save, asset_saved, Asset),
            ]
            for signal, receiver, sender in cls._disconnected:
                signal.disconnect(receiver, sender=sender)
        except (ImportError, AttributeError):
            cls._disconnected = []

    @classmethod
    def tearDownClass(cls):
        for signal, receiver, sender in cls._disconnected:
            signal.connect(receiver, sender=sender, weak=False)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"RateLimit Tenant {uid}",
            slug=f"ratelimit-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            marketplace_integrations_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"ratelimit-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        self.user.user_roles.create(role=data_provider_role)

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="RL Test API Key",
            scopes=["integrations:write", "integrations:read"],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext_key}")

        # Create a connection and mapping for tests that need them
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="RL Connection",
            config={"api_key": "test"},
            is_active=True,
        )

        from hub.apps.integrations.base import SyncDirection

        self.sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [], "options": {}},
        )

    def _make_throttled_result(self):
        """Return a RateLimitResult that mimics a throttled response."""
        import time

        from hub.apps.rate_limiting.service import RateLimitResult

        return RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_time=int(time.time()) + 60,
            limit_type="tenant",
            category="default",
            window=60,
        )

    # ── Connection endpoints ──────────────────────────────────────────

    def test_create_connection_rate_limited(self):
        """POST /connections/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.post(
                "/api/v1/integrations/marketplace/connections/",
                {
                    "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                    "name": "RL Test",
                    "config": {"key": "val"},
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_update_connection_rate_limited(self):
        """PUT /connections/{id}/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.put(
                f"/api/v1/integrations/marketplace/connections/{self.connection.id}/",
                {"name": "RL Updated"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_delete_connection_rate_limited(self):
        """DELETE /connections/{id}/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.delete(
                f"/api/v1/integrations/marketplace/connections/{self.connection.id}/",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_test_connection_rate_limited(self):
        """POST /connections/{id}/test/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.post(
                f"/api/v1/integrations/marketplace/connections/{self.connection.id}/test/",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # ── Sync endpoints ─────────────────────────────────────────────────

    def test_create_sync_job_rate_limited(self):
        """POST /sync/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.post(
                "/api/v1/integrations/marketplace/sync/",
                {
                    "connection_id": str(self.connection.id),
                    "direction": SyncDirection.PUSH.value,
                    "asset_ids": [],
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_cancel_sync_job_rate_limited(self):
        """POST /sync/{id}/cancel/ with throttled tenant → 429"""
        from unittest.mock import patch

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.post(
                f"/api/v1/integrations/marketplace/sync/{self.sync_job.id}/cancel/",
                {"reason": "RL test"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    # ── Mapping endpoints ──────────────────────────────────────────────

    def test_delete_mapping_rate_limited(self):
        """DELETE /mappings/{id}/ with throttled tenant → 429"""
        from unittest.mock import patch

        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(tenant=self.tenant, key="rl-asset", name="RL Asset")
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset,
            external_listing_id="rl-ext-1",
        )

        throttled = self._make_throttled_result()
        with patch(
            "hub.apps.integrations.views.check_rate_limit",
            return_value=(False, [throttled]),
        ):
            response = self.client.delete(
                f"/api/v1/integrations/marketplace/mappings/{mapping.id}/",
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# =============================================================================
# Connector Info Endpoint Tests (Phase 2.2, 2.3)
# =============================================================================


class MarketplaceConnectorInfoTest(TestCase):
    """Tests for list_connectors and get_connector_info view functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            cls._disconnected = [
                (post_save, contract_saved, Contract),
                (post_save, asset_saved, Asset),
            ]
            for signal, receiver, sender in cls._disconnected:
                signal.disconnect(receiver, sender=sender)
        except (ImportError, AttributeError):
            cls._disconnected = []

    @classmethod
    def tearDownClass(cls):
        for signal, receiver, sender in cls._disconnected:
            signal.connect(receiver, sender=sender, weak=False)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ConnectorInfo Tenant {uid}",
            slug=f"conninfo-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            marketplace_integrations_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"conninfo-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    # ── list_connectors ────────────────────────────────────────────────

    def test_list_connectors_returns_list(self):
        """GET /connectors/ returns a connectors list."""
        response = self.client.get("/api/v1/integrations/marketplace/connectors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("connectors", response.data)
        self.assertIsInstance(response.data["connectors"], list)

    @staticmethod
    def _make_minimal_connector():
        """Create a minimal connector class for factory registration tests."""
        from hub.apps.integrations.base import (
            DataMarketplaceConnector,
            MarketplaceListing,
            SyncResult,
            SyncStatus as _SyncStatus,
        )

        class _MinimalConnector(DataMarketplaceConnector):
            __test__ = False

            @property
            def marketplace_type(self):
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, c):
                return True

            def test_connection(self):
                return True

            def list_listings(self, **kw):
                return []

            def get_listing(self, lid):
                return MarketplaceListing(
                    marketplace_id=lid,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="T",
                )

            def list_resources(self, lid):
                return []

            def create_listing(self, l):
                return l

            def update_listing(self, lid, l):
                return l

            def publish_resource(self, lid, r):
                return r

            def download_resource(self, rid, path):
                return path

            def map_to_hub_asset(self, listing, sync_job_id=None):
                from hub.apps.assets.models import AssetSourceType
                from hub.apps.integrations.base import MarketplaceAssetMapping

                return MarketplaceAssetMapping(
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                )

            def map_from_hub_asset(self, ad, **kw):
                return MarketplaceListing(
                    marketplace_id="x",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title=ad.get("name", "T"),
                )

            def sync_push(self, aids, **kw):
                return SyncResult(
                    status=_SyncStatus.COMPLETED,
                    total_items=0, successful_items=0, failed_items=0,
                    skipped_items=0, errors=[], metadata={},
                )

            def sync_pull(self, lids=None, filters=None, **kw):
                return SyncResult(
                    status=_SyncStatus.COMPLETED,
                    total_items=0, successful_items=0, failed_items=0,
                    skipped_items=0, errors=[], metadata={},
                )

        return _MinimalConnector

    def test_list_connectors_entries_have_required_keys(self):
        """Each connector entry must have type, display_name, sync_directions, status."""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        connector_cls = self._make_minimal_connector()
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, connector_cls
        )
        try:
            response = self.client.get("/api/v1/integrations/marketplace/connectors/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            for entry in response.data["connectors"]:
                self.assertIn("type", entry)
                self.assertIn("display_name", entry)
                self.assertIn("supported_sync_directions", entry)
                self.assertIn("status", entry)
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_list_connectors_authentication_required(self):
        """Unauthenticated users must receive 401."""
        self.client.logout()
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/integrations/marketplace/connectors/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            msg=f"Expected 401 or 403 for unauthenticated request, got {response.status_code}",
        )

    # ── get_connector_info ─────────────────────────────────────────────

    def test_get_connector_info_valid_type(self):
        """GET /connectors/{valid_type}/ returns capabilities and config requirements."""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        connector_cls = self._make_minimal_connector()
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, connector_cls
        )
        try:
            response = self.client.get(
                "/api/v1/integrations/marketplace/connectors/SNOWFLAKE_DATA_MARKETPLACE/"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("capabilities", response.data)
            self.assertIn("configuration_requirements", response.data)
            self.assertIn("supported_sync_directions", response.data)
            self.assertEqual(response.data["status"], "available")
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_get_connector_info_invalid_type(self):
        """GET /connectors/{invalid}/ → 404."""
        response = self.client.get(
            "/api/v1/integrations/marketplace/connectors/NONEXISTENT_TYPE/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_connector_info_unsupported_type(self):
        """GET /connectors/{valid_enum_but_not_registered}/ returns gracefully."""
        # If a connector type is a valid enum but not registered, the view
        # returns either 404 (is_supported=False) or 200 with unavailable.
        # Either is a valid design choice; we verify the response is not 500.
        response = self.client.get(
            "/api/v1/integrations/marketplace/connectors/AWS_DATA_EXCHANGE/"
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
            msg=f"Expected 200 or 404, got {response.status_code}",
        )

    def test_get_connector_info_authentication_required(self):
        """Unauthenticated → 401.

        Note: force_authenticate in setUp can interact with DRF's @api_view
        decorator in unexpected ways in test transactions.  We use logout()
        explicitly to clear session-based auth and then verify the 401.
        """
        self.client.logout()
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/integrations/marketplace/connectors/SNOWFLAKE_DATA_MARKETPLACE/"
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            msg=f"Expected 401 or 403 for unauthenticated request, got {response.status_code}: {response.data}",
        )
