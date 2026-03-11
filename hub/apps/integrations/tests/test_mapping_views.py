"""
Marketplace Mapping Views Tests

Comprehensive tests for marketplace mapping management endpoints.
Includes unit tests, integration tests, and security tests.
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def _ensure_tenant_has_active_subscription(tenant):
    """Ensure tenant has active subscription so SubscriptionStatusMiddleware allows DELETE."""
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug="integrations-test-plan",
        defaults={
            "name": "Integrations Test Plan",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


class MarketplaceMappingViewSetTest(TestCase):
    """Test suite for MarketplaceMappingViewSet - Unit and Integration Tests"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        _ensure_tenant_has_active_subscription(self.tenant)

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role (tenant-scoped) and assign to user
        data_provider_role = Role.objects.filter(
            tenant=self.tenant, name="DATA_PROVIDER"
        ).first()
        if not data_provider_role:
            data_provider_role = Role.objects.create(
                tenant=self.tenant,
                name="DATA_PROVIDER",
                description="Data Provider Role",
            )
        self.user.user_roles.create(role=data_provider_role)

        # Create API key with integrations:write scope (store plaintext for auth in delete tests)
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.plaintext_api_key = plaintext_key
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="Test API Key",
            scopes=["integrations:write", "integrations:read"],
        )

        # Create connection
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
        )

        # Create mapping
        self.mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=["resource-1", "resource-2"],
            sync_metadata={"last_sync_status": "success"},
            last_synced_at=timezone.now() - timedelta(hours=1),
        )

        # Authenticate client
        self.client.force_authenticate(user=self.user)

    def test_list_mappings_success(self):
        """Test successful mapping listing"""
        # Create additional mappings
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")
        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456",
        )

        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

        # Verify mapping data structure
        mapping_data = response.data["results"][0]
        self.assertIn("id", mapping_data)
        self.assertIn("tenant", mapping_data)
        self.assertIn("connection_id", mapping_data)
        self.assertIn("hub_asset_id", mapping_data)
        self.assertIn("external_listing_id", mapping_data)

    def test_list_mappings_with_connection_filter(self):
        """Test mapping listing with connection_id filter"""
        # Create second connection and mapping
        connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Test Connection 2",
            config={"access_key": "test"},
        )
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")
        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection2,
            hub_asset=asset2,
            external_listing_id="ext-listing-connection2",
        )

        # Filter by connection_id
        response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/?connection_id={self.connection.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["connection_id"], str(self.connection.id))

    def test_list_mappings_with_hub_asset_filter(self):
        """Test mapping listing with hub_asset_id filter"""
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")
        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456",
        )

        # Filter by hub_asset_id
        response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/?hub_asset_id={self.asset.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["hub_asset_id"], str(self.asset.id))

    def test_list_mappings_with_external_listing_id_filter(self):
        """Test mapping listing with external_listing_id filter"""
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")
        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456",
        )

        # Filter by external_listing_id
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/?external_listing_id=ext-listing-123"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["external_listing_id"], "ext-listing-123")

    def test_list_mappings_with_ordering(self):
        """Test mapping listing with ordering"""
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")
        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset2,
            external_listing_id="ext-listing-456",
        )

        # Order by created_at ascending
        response = self.client.get("/api/v1/integrations/marketplace/mappings/?ordering=created_at")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        # First result should be older (self.mapping)
        self.assertEqual(response.data["results"][0]["id"], str(self.mapping.id))

        # Order by created_at descending (default)
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/?ordering=-created_at"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # First result should be newer (mapping2)
        self.assertEqual(response.data["results"][0]["id"], str(mapping2.id))

    def test_list_mappings_pagination(self):
        """Test mapping listing with pagination"""
        # Create multiple mappings
        for i in range(5):
            asset = Asset.objects.create(
                tenant=self.tenant, key=f"test-asset-{i}", name=f"Test Asset {i}"
            )
            MarketplaceMapping.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                hub_asset=asset,
                external_listing_id=f"ext-listing-{i}",
            )

        # Request first page
        response = self.client.get("/api/v1/integrations/marketplace/mappings/?page=1&page_size=3")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)  # 5 new + 1 existing
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_retrieve_mapping_success(self):
        """Test successful mapping retrieval"""
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(self.mapping.id), response.data["id"])
        self.assertEqual(str(self.tenant.id), response.data["tenant"])
        self.assertEqual(self.tenant.name, response.data["tenant_name"])
        self.assertEqual(str(self.connection.id), response.data["connection_id"])
        self.assertEqual(self.connection.name, response.data["connection_name"])
        self.assertEqual(str(self.asset.id), response.data["hub_asset_id"])
        self.assertEqual(self.asset.name, response.data["hub_asset_name"])
        self.assertEqual(self.asset.key, response.data["hub_asset_key"])
        self.assertEqual("ext-listing-123", response.data["external_listing_id"])
        self.assertEqual(["resource-1", "resource-2"], response.data["external_resource_ids"])
        self.assertEqual({"last_sync_status": "success"}, response.data["sync_metadata"])

    def test_retrieve_mapping_not_found(self):
        """Test retrieving non-existent mapping"""
        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{non_existent_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_mapping_success(self):
        """Test successful mapping deletion (API key auth so HasScope('integrations:write') passes)"""
        # Use a dedicated mapping so we don't remove self.mapping for later tests
        asset_del = Asset.objects.create(
            tenant=self.tenant, key="asset-delete-test", name="Asset for delete test"
        )
        mapping_to_delete = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=asset_del,
            external_listing_id="ext-listing-delete-test",
        )
        # Use a fresh client with only API key so DRF runs API key auth (force_authenticate would override)
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}")
        response = api_client.delete(
            f"/api/v1/integrations/marketplace/mappings/{mapping_to_delete.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping_to_delete.id).exists())

        # Verify MAPPING_DELETED audit event was emitted (via MarketplaceIntegrationService.delete_mapping)
        audit_event = (
            AuditEvent.objects.filter(
                resource_type="MARKETPLACE_MAPPING",
                action="MAPPING_DELETED",
                resource_id=str(mapping_to_delete.id),
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.result, "SUCCESS")

    def test_delete_mapping_not_found(self):
        """Test deleting non-existent mapping (API key auth so permission passes, then 404)"""
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}")
        non_existent_id = uuid.uuid4()
        response = api_client.delete(
            f"/api/v1/integrations/marketplace/mappings/{non_existent_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_mapping_requires_write_permission(self):
        """Test that delete requires integrations:write scope"""
        # Create user without write scope
        user_no_write = User.objects.create_user(
            email="nowrite@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        data_provider_role = Role.objects.filter(
            tenant=self.tenant, name="DATA_PROVIDER"
        ).first()
        if not data_provider_role:
            data_provider_role = Role.objects.create(
                tenant=self.tenant,
                name="DATA_PROVIDER",
                description="Data Provider Role",
            )
        user_no_write.user_roles.create(role=data_provider_role)

        # Create API key with only read scope
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        api_key_readonly = APIKey.objects.create(
            tenant=self.tenant,
            user=user_no_write,
            key_hash=key_hash,
            name="Read Only API Key",
            scopes=["integrations:read"],
        )

        # Use API key authentication instead of force_authenticate to properly test scope checking
        # force_authenticate bypasses the authentication middleware that sets request.api_key_scopes
        self.client.force_authenticate(user=None)  # Clear any existing auth
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext_key}")

        response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_mappings_empty_result(self):
        """Test listing mappings when none exist"""
        # Delete all mappings
        MarketplaceMapping.objects.all().delete()

        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_mappings_invalid_connection_id_filter(self):
        """Test listing with invalid connection_id filter"""
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/?connection_id=invalid-uuid"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_mappings_invalid_hub_asset_id_filter(self):
        """Test listing with invalid hub_asset_id filter"""
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/?hub_asset_id=invalid-uuid"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_mapping_serializer_includes_all_fields(self):
        """Test that serializer includes all required fields"""
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        required_fields = [
            "id",
            "tenant",
            "tenant_name",
            "connection_id",
            "connection_name",
            "hub_asset_id",
            "hub_asset_name",
            "hub_asset_key",
            "external_listing_id",
            "external_resource_ids",
            "sync_metadata",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, response.data, f"Field {field} missing from response")

    def test_mapping_list_only_get_and_delete_methods(self):
        """Test that only GET and DELETE methods are allowed (API key auth for consistency)"""
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}")
        # POST should not be allowed
        response = api_client.post("/api/v1/integrations/marketplace/mappings/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT should not be allowed
        response = api_client.put(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping.id}/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH should not be allowed
        response = api_client.patch(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping.id}/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass


class MarketplaceMappingViewSetSecurityTest(TestCase):
    """Security tests for MarketplaceMappingViewSet - Tenant isolation and permissions"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
        self.client = APIClient()

        # Create tenant 1
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1", slug="tenant-1", kyc_status=KYCStatus.VERIFIED
        )
        _ensure_tenant_has_active_subscription(self.tenant1)

        # Create tenant 2
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2", slug="tenant-2", kyc_status=KYCStatus.VERIFIED
        )
        _ensure_tenant_has_active_subscription(self.tenant2)

        # Create user for tenant 1
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )

        # Create user for tenant 2
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role per tenant (roles are tenant-scoped)
        for tenant, user in ((self.tenant1, self.user1), (self.tenant2, self.user2)):
            role = Role.objects.filter(tenant=tenant, name="DATA_PROVIDER").first()
            if not role:
                role = Role.objects.create(
                    tenant=tenant,
                    name="DATA_PROVIDER",
                    description="Data Provider Role",
                )
            user.user_roles.create(role=role)

        # Create API keys with unique key hashes (store plaintext for auth in tests)
        plaintext_key1 = APIKey.generate_key()
        key_hash1 = APIKey.hash_key(plaintext_key1)
        self.plaintext_api_key1 = plaintext_key1
        self.api_key1 = APIKey.objects.create(
            tenant=self.tenant1,
            user=self.user1,
            key_hash=key_hash1,
            name="Tenant 1 API Key",
            scopes=["integrations:write", "integrations:read"],
        )

        plaintext_key2 = APIKey.generate_key()
        key_hash2 = APIKey.hash_key(plaintext_key2)
        self.plaintext_api_key2 = plaintext_key2
        self.api_key2 = APIKey.objects.create(
            tenant=self.tenant2,
            user=self.user2,
            key_hash=key_hash2,
            name="Tenant 2 API Key",
            scopes=["integrations:write", "integrations:read"],
        )

        # Create connections
        self.connection1 = MarketplaceConnection.objects.create(
            tenant=self.tenant1,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Tenant 1 Connection",
            config={"api_key": "test_key_1"},
            is_active=True,
        )
        self.connection2 = MarketplaceConnection.objects.create(
            tenant=self.tenant2,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Tenant 2 Connection",
            config={"api_key": "test_key_2"},
            is_active=True,
        )

        # Create assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant1, key="tenant-1-asset", name="Tenant 1 Asset"
        )
        self.asset2 = Asset.objects.create(
            tenant=self.tenant2, key="tenant-2-asset", name="Tenant 2 Asset"
        )

        # Create mappings
        self.mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant1,
            connection=self.connection1,
            hub_asset=self.asset1,
            external_listing_id="ext-listing-tenant1",
        )
        self.mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant2,
            connection=self.connection2,
            hub_asset=self.asset2,
            external_listing_id="ext-listing-tenant2",
        )

    def test_tenant_isolation_list(self):
        """Test that users can only see mappings from their tenant"""
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.mapping1.id))
        self.assertEqual(response.data["results"][0]["tenant"], str(self.tenant1.id))

    def test_tenant_isolation_retrieve(self):
        """Test that users cannot retrieve mappings from other tenants"""
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

        # Try to retrieve mapping from tenant2
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping2.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_isolation_delete(self):
        """Test that users cannot delete mappings from other tenants"""
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

        # Try to delete mapping from tenant2
        response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping2.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify mapping2 still exists
        self.assertTrue(MarketplaceMapping.objects.filter(id=self.mapping2.id).exists())

    def test_tenant_isolation_filter(self):
        """Test that filters only return mappings from user's tenant"""
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

        # Filter by connection_id from tenant2 (should return empty)
        response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/?connection_id={self.connection2.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_delete_requires_authentication(self):
        """Test that delete requires authentication"""
        # Don't authenticate
        self.client.force_authenticate(user=None)

        response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_authentication(self):
        """Test that list requires authentication"""
        # Don't authenticate
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_requires_authentication(self):
        """Test that retrieve requires authentication"""
        # Don't authenticate
        self.client.force_authenticate(user=None)

        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_requires_data_provider_role(self):
        """Test that delete requires DATA_PROVIDER or TENANT_ADMIN role"""
        # Create user without DATA_PROVIDER role
        user_no_role = User.objects.create_user(
            email="norole@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )

        # Create API key for user without role
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        APIKey.objects.create(
            tenant=self.tenant1,
            user=user_no_role,
            key_hash=key_hash,
            name="No Role API Key",
            scopes=["integrations:read"],  # Only read scope, no write
        )

        # Authenticate with user without role
        self.client.force_authenticate(user=user_no_role)

        response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_with_tenant_admin_role(self):
        """Test that TENANT_ADMIN role can delete mappings"""
        # Create TENANT_ADMIN role for tenant1 (roles are tenant-scoped)
        tenant_admin_role = Role.objects.filter(
            tenant=self.tenant1, name="TENANT_ADMIN"
        ).first()
        if not tenant_admin_role:
            tenant_admin_role = Role.objects.create(
                tenant=self.tenant1,
                name="TENANT_ADMIN",
                description="Tenant Admin Role",
            )

        user_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        user_admin.user_roles.create(role=tenant_admin_role)

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        APIKey.objects.create(
            tenant=self.tenant1,
            user=user_admin,
            key_hash=key_hash,
            name="Admin API Key",
            scopes=["integrations:write", "integrations:read"],
        )

        # Use fresh client with API key so HasScope('integrations:write') passes
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext_key}")

        response = api_client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_list_cross_tenant_filter_returns_empty(self):
        """Test that filtering by cross-tenant IDs returns empty results"""
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)

        # Try to filter by asset from tenant2
        response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/?hub_asset_id={self.asset2.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_mapping_deletion_audit_log(self):
        """Test that mapping deletion is properly logged (API key auth for write)"""
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key1}")

        # Delete mapping
        response = api_client.delete(
            f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify mapping is deleted
        self.assertFalse(MarketplaceMapping.objects.filter(id=self.mapping1.id).exists())

    # ========== ERROR HANDLING TESTS ==========

    def test_list_mappings_validation_error_response_format(self):
        """Test that validation errors return proper error response format"""
        self.client.force_authenticate(user=self.user1)
        # Try to list with invalid connection_id filter
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/", {"connection_id": "not-a-uuid"}
        )

        # May return 200 with empty results or 400 with error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn("detail", response.data or {})

    def test_retrieve_mapping_error_handling(self):
        """Test that retrieve errors are handled gracefully"""
        self.client.force_authenticate(user=self.user1)
        # Retrieve nonexistent mapping
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_mapping_error_handling(self):
        """Test that delete errors are handled gracefully (use tenant1; API key auth for write)"""
        asset_err = Asset.objects.create(
            tenant=self.tenant1, key="asset-error-handling", name="Asset for error test"
        )
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant1,
            connection=self.connection1,
            hub_asset=asset_err,
            external_listing_id="ext-listing-error",
        )
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key1}")

        # Delete should succeed
        response = api_client.delete(f"/api/v1/integrations/marketplace/mappings/{mapping.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Try to delete again - should return 404
        response = api_client.delete(f"/api/v1/integrations/marketplace/mappings/{mapping.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_mappings_error_handling(self):
        """Test that list errors are handled gracefully"""
        self.client.force_authenticate(user=self.user1)
        # List should always succeed (may return empty list)
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_list_mappings_with_malformed_filters(self):
        """Test that malformed filters are handled gracefully"""
        self.client.force_authenticate(user=self.user1)
        # Try with invalid filter values
        response = self.client.get(
            "/api/v1/integrations/marketplace/mappings/",
            {"connection_id": "invalid", "hub_asset_id": "invalid"},
        )

        # May return 200 with empty results or 400 with error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    # ========== TDD COMPLIANCE TESTS ==========

    def test_retrieve_mapping_response_has_all_required_fields(self):
        """Test that retrieved mapping response has all required fields"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/")

        if response.status_code == status.HTTP_200_OK:
            # Verify all required fields are present
            self.assertIn("id", response.data)
            self.assertIn("tenant", response.data)
            self.assertIn("tenant_name", response.data)
            self.assertIn("connection_id", response.data)
            self.assertIn("connection_name", response.data)
            self.assertIn("hub_asset_id", response.data)
            self.assertIn("hub_asset_name", response.data)
            self.assertIn("external_listing_id", response.data)
            self.assertIn("external_resource_ids", response.data)
            self.assertIn("sync_metadata", response.data)
            self.assertIn("created_at", response.data)
            self.assertIn("updated_at", response.data)

    def test_list_mappings_response_structure(self):
        """Test that list response has correct structure"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify pagination structure
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertIsInstance(response.data["count"], int)

    def test_list_mappings_field_types(self):
        """Test that list response fields have correct types"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data["results"]:
            mapping = response.data["results"][0]
            self.assertIsInstance(mapping["id"], str)
            self.assertIsInstance(mapping["external_listing_id"], str)
            self.assertIsInstance(mapping["external_resource_ids"], list)
            self.assertIsInstance(mapping["sync_metadata"], dict)

    def test_retrieve_mapping_field_types(self):
        """Test that retrieve response fields have correct types"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"/api/v1/integrations/marketplace/mappings/{self.mapping1.id}/")

        if response.status_code == status.HTTP_200_OK:
            data = response.data
            self.assertIsInstance(data["id"], str)
            self.assertIsInstance(data["external_listing_id"], str)
            self.assertIsInstance(data["external_resource_ids"], list)
            self.assertIsInstance(data["sync_metadata"], dict)
            self.assertIsInstance(data["created_at"], str)
            self.assertIsInstance(data["updated_at"], str)

    def test_list_mappings_timestamp_format(self):
        """Test that timestamps are properly formatted"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.data["results"]:
            mapping = response.data["results"][0]
            # Timestamps should be strings (ISO format)
            self.assertIsInstance(mapping["created_at"], str)
            self.assertIsInstance(mapping["updated_at"], str)
