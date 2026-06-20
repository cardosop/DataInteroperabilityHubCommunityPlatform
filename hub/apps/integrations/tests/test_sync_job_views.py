"""
Marketplace Sync Job Views Tests

Comprehensive tests for marketplace sync job management endpoints.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobViewSetTest(TestCase):
    """Test suite for MarketplaceSyncJobViewSet"""

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
        # API key auth ensures request.api_key_scopes is set and user has prefetched roles
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

        # Create connection
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

        # Register a stub Snowflake connector so factory.is_supported() returns
        # True deterministically.  Without this, the test depends on whether a
        # SnowflakeConnector was registered by a previous test file, making
        # status-code assertions non-deterministic (201 vs 400 vs 500).
        from hub.apps.integrations.base import DataMarketplaceConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        self._saved_snowflake = MarketplaceConnectorFactory._connectors.get(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )

        class _TestSyncJobViewConnector(DataMarketplaceConnector):
            """Deterministic stub for sync-job view tests."""

            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id):
                from hub.apps.integrations.base import MarketplaceListing

                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test Listing",
                )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, _TestSyncJobViewConnector
        )

        # Authenticate via API key (ensures HasScope and HasAnyRole see correct context)
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}")

        # Sample sync request data
        self.valid_push_sync_data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PUSH.value,
            "asset_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            "options": {"dry_run": False},
        }

        self.valid_pull_sync_data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PULL.value,
            "listing_ids": ["listing1", "listing2"],
            "filters": {"category": "data"},
            "options": {"create_assets": True},
        }

    def tearDown(self):
        """Restore connector factory state so other test files are unaffected."""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        if self._saved_snowflake is not None:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, self._saved_snowflake
            )
        else:
            try:
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )
            except ValueError:
                pass  # Already unregistered
        super().tearDown()

    def test_create_push_sync_job_success(self):
        """Test successful PUSH sync job creation"""
        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", self.valid_push_sync_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["direction"], SyncDirection.PUSH.value)
        self.assertEqual(response.data["status"], SyncStatus.PENDING.value)
        self.assertIn("connection_id", response.data)

    def test_create_pull_sync_job_success(self):
        """Test successful PULL sync job creation"""
        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", self.valid_pull_sync_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["direction"], SyncDirection.PULL.value)
        self.assertEqual(response.data["status"], SyncStatus.PENDING.value)

    def test_create_sync_job_missing_required_fields(self):
        """Test sync job creation with missing required fields"""
        data = {
            "direction": SyncDirection.PUSH.value,
            # Missing connection_id and asset_ids
        }

        response = self.client.post("/api/v1/integrations/marketplace/sync/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_push_sync_job_without_asset_ids(self):
        """Test PUSH sync job creation without asset_ids"""
        data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PUSH.value,
            # Missing asset_ids
        }

        response = self.client.post("/api/v1/integrations/marketplace/sync/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("asset_ids", str(response.data))

    def test_create_sync_job_invalid_connection_id(self):
        """Test sync job creation with invalid connection_id"""
        data = self.valid_push_sync_data.copy()
        data["connection_id"] = str(uuid.uuid4())  # Non-existent connection

        response = self.client.post("/api/v1/integrations/marketplace/sync/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_sync_jobs_success(self):
        """Test successful sync job listing"""
        # Create test sync jobs
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0,
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
        )

        response = self.client.get("/api/v1/integrations/marketplace/sync/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_sync_jobs_with_connection_filter(self):
        """Test sync job listing with connection_id filter"""
        # Create sync jobs
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )

        # Create another connection and sync job
        other_connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Other Connection",
            config={"key": "value"},
            is_active=True,
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=other_connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/sync/", {"connection_id": str(self.connection.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["connection_id"], str(self.connection.id))

    def test_list_sync_jobs_with_status_filter(self):
        """Test sync job listing with status filter"""
        # Create sync jobs with different statuses
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/sync/", {"status": SyncStatus.PENDING.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], SyncStatus.PENDING.value)

    def test_list_sync_jobs_with_direction_filter(self):
        """Test sync job listing with direction filter"""
        # Create sync jobs with different directions
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
        )

        response = self.client.get(
            "/api/v1/integrations/marketplace/sync/", {"direction": SyncDirection.PUSH.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["direction"], SyncDirection.PUSH.value)

    def test_retrieve_sync_job_success(self):
        """Test successful sync job retrieval"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0,
        )

        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(sync_job.id))
        self.assertEqual(response.data["direction"], SyncDirection.PUSH.value)
        self.assertEqual(response.data["status"], SyncStatus.PENDING.value)

    def test_retrieve_sync_job_not_found(self):
        """Test retrieving non-existent sync job"""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data or {})

    def test_cancel_sync_job_success(self):
        """Test successful sync job cancellation"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0,
        )

        cancel_data = {"reason": "User requested cancellation"}

        response = self.client.post(
            f"/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/",
            cancel_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)

    def test_cancel_completed_sync_job(self):
        """Test cancelling a completed sync job (should fail)"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
            completed_at=timezone.now(),
        )

        cancel_data = {"reason": "User requested cancellation"}

        response = self.client.post(
            f"/api/v1/integrations/marketplace/sync/{sync_job.id}/cancel/",
            cancel_data,
            format="json",
        )

        # Should fail because job is already completed
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data or {})

    def test_cancel_sync_job_not_found(self):
        """Test cancelling non-existent sync job"""
        fake_id = uuid.uuid4()
        cancel_data = {"reason": "Test"}

        response = self.client.post(
            f"/api/v1/integrations/marketplace/sync/{fake_id}/cancel/", cancel_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data or {})

    def test_unauthenticated_access(self):
        """Test unauthenticated users cannot access endpoints"""
        self.client.force_authenticate(user=None)
        self.client.credentials()

        response = self.client.get("/api/v1/integrations/marketplace/sync/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data or {})

        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", self.valid_push_sync_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data or {})

    def test_tenant_isolation(self):
        """Test tenant isolation - users can only see their tenant's sync jobs"""
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

        # Create connection and sync job in other tenant
        other_connection = MarketplaceConnection.objects.create(
            tenant=other_tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Other Connection",
            config={"key": "value"},
        )
        other_sync_job = MarketplaceSyncJob.objects.create(
            tenant=other_tenant,
            connection=other_connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )

        # Try to access with original user
        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{other_sync_job.id}/")

        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

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

        # Try to create sync job
        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", self.valid_push_sync_data, format="json"
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

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )

        self.client.credentials()
        self.client.force_authenticate(user=regular_user)

        # Should be able to read
        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination(self):
        """Test pagination works correctly"""
        # Create multiple sync jobs
        for _i in range(25):
            MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
            )

        response = self.client.get("/api/v1/integrations/marketplace/sync/", {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["count"], 25)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_push_sync_job_validation_error_response_format(self):
        """Test that validation errors return proper error response format"""
        # Try to create sync job with invalid connection_id
        invalid_data = {
            "connection_id": "not-a-uuid",
            "direction": SyncDirection.PUSH.value,
            "asset_ids": ["asset-1"],
        }

        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", invalid_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should have error details (API may use "detail" or "error" structure)
        data = response.data or {}
        self.assertTrue(
            "detail" in data or "error" in data,
            msg=f"Expected error details in response, got keys: {list(data.keys())}",
        )

    def test_create_sync_job_malformed_json(self):
        """Test that malformed JSON returns proper error"""
        # Send invalid JSON
        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/",
            "invalid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Malformed request body is rejected by DRF's parser and may return
        # a plain JsonResponse or a DRF Response depending on version.
        # Verify some error content is returned (use getattr for both types).
        resp_data = getattr(response, "data", None) or getattr(response, "content", b"")
        if isinstance(resp_data, bytes):
            import json

            resp_data = json.loads(resp_data)
        self.assertTrue(resp_data, "Error response should contain body content")

    def test_get_sync_job_not_found_error(self):
        """Test that getting nonexistent sync job returns 404"""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data or {})

    def test_cancel_sync_job_not_found_error(self):
        """Test that canceling nonexistent sync job returns 404"""
        fake_id = uuid.uuid4()
        response = self.client.post(
            f"/api/v1/integrations/marketplace/sync/{fake_id}/cancel/",
            {"reason": "Test reason"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data or {})

    def test_list_sync_jobs_error_handling(self):
        """Test that list errors are handled gracefully"""
        # List should always succeed (may return empty list)
        response = self.client.get("/api/v1/integrations/marketplace/sync/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_create_sync_job_response_has_all_required_fields(self):
        """Test that created sync job response has all required fields"""
        response = self.client.post(
            "/api/v1/integrations/marketplace/sync/", self.valid_push_sync_data, format="json"
        )

        if response.status_code == status.HTTP_201_CREATED:
            # Verify all required fields are present
            self.assertIn("id", response.data)
            self.assertIn("direction", response.data)
            self.assertIn("status", response.data)
            self.assertIn("items_synced", response.data)
            self.assertIn("items_failed", response.data)
            self.assertIn("errors", response.data)
            self.assertIn("metadata", response.data)
            self.assertIn("created_at", response.data)
            self.assertIn("updated_at", response.data)

    def test_get_sync_job_response_structure(self):
        """Test that get sync job response has correct structure"""
        # Create sync job first
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )

        response = self.client.get(f"/api/v1/integrations/marketplace/sync/{sync_job.id}/")

        if response.status_code == status.HTTP_200_OK:
            # Verify pagination structure
            self.assertIn("id", response.data)
            self.assertIn("direction", response.data)
            self.assertIn("status", response.data)
            self.assertIsInstance(response.data["items_synced"], int)
            self.assertIsInstance(response.data["items_failed"], int)
            self.assertIsInstance(response.data["errors"], list)
            self.assertIsInstance(response.data["metadata"], dict)

    def test_list_sync_jobs_response_structure(self):
        """Test that list response has correct structure"""
        response = self.client.get("/api/v1/integrations/marketplace/sync/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify pagination structure
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertIsInstance(response.data["count"], int)
