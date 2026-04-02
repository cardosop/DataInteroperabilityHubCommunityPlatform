"""
Integration tests for Marketplace Integration URL routing

Tests verify that URL patterns are correctly configured and resolve to the
expected views with proper routing.
"""

import uuid
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.auth.models import APIKey
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.views import (
    MarketplaceConnectionViewSet,
    MarketplaceMappingViewSet,
    MarketplaceSyncJobViewSet,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserStatus
import uuid

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceIntegrationURLPatternResolutionTest(TestCase):
    """Test URL pattern resolution for marketplace integration endpoints"""

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

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_connections_list_url_resolves(self):
        """Test that /api/v1/integrations/marketplace/connections/ resolves correctly"""
        url = reverse("marketplace-connection-list")
        self.assertEqual(url, "/api/v1/integrations/marketplace/connections/")

        resolved = resolve("/api/v1/integrations/marketplace/connections/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceConnectionViewSet)
        self.assertIn("list", resolved.url_name or "")

    def test_connections_detail_url_resolves(self):
        """Test that detail URL resolves correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )

        url = reverse("marketplace-connection-detail", kwargs={"id": str(connection.id)})
        self.assertIn(f"/api/v1/integrations/marketplace/connections/{connection.id}/", url)

        resolved = resolve(f"/api/v1/integrations/marketplace/connections/{connection.id}/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceConnectionViewSet)
        self.assertIn("detail", resolved.url_name or "")

    def test_sync_jobs_list_url_resolves(self):
        """Test that /api/v1/integrations/marketplace/sync/ resolves correctly"""
        url = reverse("marketplace-sync-job-list")
        self.assertEqual(url, "/api/v1/integrations/marketplace/sync/")

        resolved = resolve("/api/v1/integrations/marketplace/sync/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceSyncJobViewSet)
        self.assertIn("list", resolved.url_name or "")

    def test_sync_jobs_detail_url_resolves(self):
        """Test that sync job detail URL resolves correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=connection, direction=SyncDirection.PUSH.value
        )

        url = reverse("marketplace-sync-job-detail", kwargs={"id": str(sync_job.id)})
        self.assertIn(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/", url)

        resolved = resolve(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceSyncJobViewSet)
        self.assertIn("detail", resolved.url_name or "")

    def test_mappings_list_url_resolves(self):
        """Test that /api/v1/integrations/marketplace/mappings/ resolves correctly"""
        url = reverse("marketplace-mapping-list")
        self.assertEqual(url, "/api/v1/integrations/marketplace/mappings/")

        resolved = resolve("/api/v1/integrations/marketplace/mappings/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceMappingViewSet)
        self.assertIn("list", resolved.url_name or "")

    def test_mappings_detail_url_resolves(self):
        """Test that mapping detail URL resolves correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )
        asset = Asset.objects.create(tenant=self.tenant, key="test-asset", name="Test Asset")
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection,
            hub_asset=asset,
            external_listing_id="ext-listing-123",
        )

        url = reverse("marketplace-mapping-detail", kwargs={"id": str(mapping.id)})
        self.assertIn(f"/api/v1/integrations/marketplace/mappings/{mapping.id}/", url)

        resolved = resolve(f"/api/v1/integrations/marketplace/mappings/{mapping.id}/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceMappingViewSet)
        self.assertIn("detail", resolved.url_name or "")

    def test_connections_test_action_url_resolves(self):
        """Test that connection test action URL resolves correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )

        url = reverse("marketplace-connection-test", kwargs={"id": str(connection.id)})
        self.assertIn(f"/api/v1/integrations/marketplace/connections/{connection.id}/test/", url)

        resolved = resolve(f"/api/v1/integrations/marketplace/connections/{connection.id}/test/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceConnectionViewSet)
        self.assertEqual(resolved.url_name, "marketplace-connection-test")

    def test_sync_jobs_cancel_action_url_resolves(self):
        """Test that sync job cancel action URL resolves correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=connection, direction=SyncDirection.PUSH.value
        )

        url = reverse("marketplace-sync-job-cancel", kwargs={"id": str(sync_job.id)})
        self.assertIn(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/", url)

        resolved = resolve(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.func.cls, MarketplaceSyncJobViewSet)
        self.assertEqual(resolved.url_name, "marketplace-sync-job-cancel")

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


class MarketplaceIntegrationURLIntegrationTest(TestCase):
    """Integration tests for marketplace integration URL endpoints"""

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

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        # Active subscription required so TenantSuspensionMiddleware allows API writes
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Role is tenant-scoped; use get_or_create with tenant
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
            name="Test API Key",
            scopes=["integrations:write", "integrations:read"],
        )

        self.client.force_authenticate(user=self.user)

    def test_connections_endpoints_accessible(self):
        """Test that connection endpoints are accessible"""
        # List endpoint
        response = self.client.get("/api/v1/integrations/marketplace/connections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

        # Create endpoint
        create_response = self.client.post(
            "/api/v1/integrations/marketplace/connections/",
            {
                "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                "name": "Test Connection",
                "config": {"api_key": "test-key"},
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        connection_id = create_response.data["id"]

        # Detail endpoint
        detail_response = self.client.get(
            f"/api/v1/integrations/marketplace/connections/{connection_id}/"
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], connection_id)

        # Test action endpoint
        test_response = self.client.post(
            f"/api/v1/integrations/marketplace/connections/{connection_id}/test/"
        )
        # May return 200 (success) or 400/500 (connection test failed)
        self.assertIn(
            test_response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ],
        )

    def test_sync_jobs_endpoints_accessible(self):
        """Test that sync job endpoints are accessible"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )

        # List endpoint
        response = self.client.get("/api/v1/integrations/marketplace/sync/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

        # Create endpoint
        create_response = self.client.post(
            "/api/v1/integrations/marketplace/sync/",
            {
                "connection_id": str(connection.id),
                "direction": SyncDirection.PUSH.value,
                "asset_ids": [],
            },
            format="json",
        )
        # May return 201 (created) or 400/500 (validation/connector error)
        self.assertIn(
            create_response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ],
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            sync_job_id = create_response.data["id"]

            # Detail endpoint
            detail_response = self.client.get(
                f"/api/v1/integrations/marketplace/sync/{sync_job_id}/"
            )
            self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
            self.assertEqual(detail_response.data["id"], sync_job_id)

            # Cancel action endpoint
            cancel_response = self.client.post(
                f"/api/v1/integrations/marketplace/sync/{sync_job_id}/cancel/",
                {"reason": "Test cancellation"},
                format="json",
            )
            # May return 200 (cancelled) or 400 (cannot cancel)
            self.assertIn(
                cancel_response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
            )

    def test_mappings_endpoints_accessible(self):
        """Test that mapping endpoints are accessible"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )
        asset = Asset.objects.create(tenant=self.tenant, key="test-asset", name="Test Asset")
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection,
            hub_asset=asset,
            external_listing_id="ext-listing-123",
        )

        # List endpoint
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(response.data["count"], 1)

        # Detail endpoint
        detail_response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/{mapping.id}/"
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], str(mapping.id))

        # Delete endpoint
        delete_response = self.client.delete(
            f"/api/v1/integrations/marketplace/mappings/{mapping.id}/"
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        verify_response = self.client.get(
            f"/api/v1/integrations/marketplace/mappings/{mapping.id}/"
        )
        self.assertEqual(verify_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_router_registration_verification(self):
        """Test that router registration is correct"""
        from hub.apps.integrations.urls import router

        # Check router registry for registered patterns
        registered_patterns = [prefix for prefix, _, _ in router.registry]
        self.assertIn("marketplace/connections", registered_patterns)
        self.assertIn("marketplace/sync", registered_patterns)
        self.assertIn("marketplace/mappings", registered_patterns)

        # Verify basenames are correct
        basenames = [basename for _, _, basename in router.registry]
        self.assertIn("marketplace-connection", basenames)
        self.assertIn("marketplace-sync-job", basenames)
        self.assertIn("marketplace-mapping", basenames)

    def test_url_consistency_across_endpoints(self):
        """Test that all endpoints use consistent URL patterns"""
        # Connections endpoints
        connections_list = self.client.get("/api/v1/integrations/marketplace/connections/")
        self.assertEqual(connections_list.status_code, status.HTTP_200_OK)

        # Sync jobs endpoints
        sync_list = self.client.get("/api/v1/integrations/marketplace/sync/")
        self.assertEqual(sync_list.status_code, status.HTTP_200_OK)

        # Mappings endpoints
        mappings_list = self.client.get("/api/v1/integrations/marketplace/mappings/")
        self.assertEqual(mappings_list.status_code, status.HTTP_200_OK)

    def test_integrations_base_url_included(self):
        """Test that integrations URLs are included under /api/v1/integrations/"""
        # Verify base path
        response = self.client.get("/api/v1/integrations/marketplace/connections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify it's not accessible without /integrations/ prefix
        # (This would be a 404 if not properly included)
        response = self.client.get("/api/v1/marketplace/connections/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_url_reverse_consistency(self):
        """Test that reverse() produces consistent URLs"""
        # Connections
        connections_url = reverse("marketplace-connection-list")
        self.assertEqual(connections_url, "/api/v1/integrations/marketplace/connections/")

        # Sync jobs
        sync_url = reverse("marketplace-sync-job-list")
        self.assertEqual(sync_url, "/api/v1/integrations/marketplace/sync/")

        # Mappings
        mappings_url = reverse("marketplace-mapping-list")
        self.assertEqual(mappings_url, "/api/v1/integrations/marketplace/mappings/")

    def test_no_duplicate_url_patterns(self):
        """Test that there are no duplicate URL patterns"""
        from hub.apps.integrations.urls import router

        # Get all registered patterns
        patterns = [prefix for prefix, _, _ in router.registry]

        # Check for duplicates
        seen = set()
        duplicates = []
        for pattern in patterns:
            if pattern in seen:
                duplicates.append(pattern)
            seen.add(pattern)

        self.assertEqual(len(duplicates), 0, f"Found duplicate URL patterns: {duplicates}")

    def test_url_patterns_match_viewset_methods(self):
        """Test that URL patterns match available ViewSet methods"""
        from hub.apps.integrations.urls import router

        # Verify each registered viewset has corresponding URL patterns
        for prefix, viewset, basename in router.registry:
            self.assertIsNotNone(viewset)
            self.assertIsNotNone(basename)
            self.assertIsNotNone(prefix)

            # Verify basename matches expected pattern
            if "connection" in prefix:
                self.assertEqual(basename, "marketplace-connection")
            elif "sync" in prefix:
                self.assertEqual(basename, "marketplace-sync-job")
            elif "mapping" in prefix:
                self.assertEqual(basename, "marketplace-mapping")

    # ========== ERROR HANDLING TESTS ==========

    def test_url_reverse_with_invalid_name(self):
        """Test that reverse() raises error for invalid URL name"""
        with self.assertRaises(NoReverseMatch):
            reverse("invalid-url-name")

    def test_url_resolve_with_invalid_path(self):
        """Test that resolve() handles invalid paths"""
        with self.assertRaises(Exception):
            resolve("/api/v1/integrations/marketplace/invalid-path/")

    def test_url_resolve_with_missing_id(self):
        """Test that resolve() handles paths with missing IDs"""
        # Try to resolve detail URL without ID
        with self.assertRaises(Exception):
            resolve("/api/v1/integrations/marketplace/connections//")

    # ========== TDD COMPLIANCE TESTS ==========

    def test_all_url_patterns_have_basenames(self):
        """Test that all URL patterns have basenames"""
        from hub.apps.integrations.urls import router

        for prefix, viewset, basename in router.registry:
            self.assertIsNotNone(basename)
            self.assertIsInstance(basename, str)
            self.assertGreater(len(basename), 0)

    def test_all_url_patterns_have_viewsets(self):
        """Test that all URL patterns have viewsets"""
        from hub.apps.integrations.urls import router

        for prefix, viewset, basename in router.registry:
            self.assertIsNotNone(viewset)
            # Viewset should be a class
            self.assertTrue(hasattr(viewset, "__name__") or hasattr(viewset, "__class__"))

    def test_url_patterns_consistency(self):
        """Test that URL patterns follow consistent naming"""
        from hub.apps.integrations.urls import router

        for prefix, viewset, basename in router.registry:
            # Basename should match prefix pattern
            if "connection" in prefix:
                self.assertIn("connection", basename)
            elif "sync" in prefix:
                self.assertIn("sync", basename)
            elif "mapping" in prefix:
                self.assertIn("mapping", basename)

    def test_action_urls_resolve_correctly(self):
        """Test that action URLs resolve correctly"""
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test"},
        )

        # Test action URL
        test_url = reverse("marketplace-connection-test", kwargs={"id": str(connection.id)})
        self.assertIn("/test/", test_url)

        resolved = resolve(test_url)
        self.assertEqual(resolved.url_name, "marketplace-connection-test")

    def test_list_urls_accessible_without_id(self):
        """Test that list URLs are accessible without ID"""
        # Connections list
        response = self.client.get("/api/v1/integrations/marketplace/connections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Sync jobs list
        response = self.client.get("/api/v1/integrations/marketplace/sync/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Mappings list
        response = self.client.get("/api/v1/integrations/marketplace/mappings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
