"""
Unit tests for asset CRUD operations.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetCRUDTest(TestCase):
    """Test asset CRUD operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        # Active subscription required so TenantSuspensionMiddleware allows writes.
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user with DATA_PROVIDER role (required for asset create/update)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)

    def _unique_key(self, prefix: str = "test-asset") -> str:
        """Return a tenant-unique asset key for test isolation.

        Using UUID-based keys prevents cascading UniqueViolation
        failures if a prior test's transaction rollback fails.
        """
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    def test_create_asset_returns_201(self):
        """Test creating an asset returns 201 status code"""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_asset_returns_correct_response_data_has_id(self):
        """Test creating an asset returns response data with id."""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertIn("id", response.data)

    def test_create_asset_returns_correct_response_data_has_key(self):
        """Test creating an asset returns response data with key."""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.data["key"], test_key)

    def test_create_asset_returns_correct_response_data_has_name(self):
        """Test creating an asset returns response data with name."""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.data["name"], "Test Asset")

    def test_create_asset_returns_correct_response_data_has_version(self):
        """Test creating an asset returns response data with version."""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.data["version"], 1)

    def test_create_asset_sets_default_status_values(self):
        """Test creating an asset sets default status values"""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.data["status"], AssetStatus.DRAFT)
        self.assertEqual(response.data["dq_status"], DQStatus.UNKNOWN)
        self.assertEqual(response.data["compliance_status"], ComplianceStatus.UNKNOWN)

    def test_create_asset_sets_tenant_and_created_by(self):
        """Test creating an asset sets tenant and created_by correctly"""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {
            "key": test_key,
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
        }

        response = self.client.post("/api/v1/assets/", data, format="json")

        # Verify asset was created with correct tenant and user
        asset_id = response.data["id"]
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.tenant, self.tenant)
        self.assertEqual(asset.created_by, self.user)

    def test_create_asset_duplicate_key(self):
        """Test creating asset with duplicate key fails"""
        self.client.force_authenticate(user=self.user)

        # Create first asset
        dup_key = self._unique_key("dup")
        Asset.objects.create(
            tenant=self.tenant, key=dup_key, name="First Asset", created_by=self.user
        )

        # Try to create second asset with same key
        data = {"key": dup_key, "name": "Second Asset"}

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
            msg="Duplicate key should return 400 or 409",
        )
        # Response may have "error" or "detail" key
        error_msg = response.data.get("error") or response.data.get("detail", "")
        self.assertTrue(
            "already exists" in str(error_msg).lower()
            or response.data.get("code") in ("CONFLICT", "CONFLICT_ERROR"),
            msg="Response should indicate duplicate/conflict",
        )

    def test_retrieve_asset_returns_200(self):
        """Test retrieving an asset returns 200 status code"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        response = self.client.get(f"/api/v1/assets/{asset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_asset_returns_correct_data(self):
        """Test retrieving an asset returns correct data"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        response = self.client.get(f"/api/v1/assets/{asset.id}/")

        self.assertEqual(response.data["id"], str(asset.id))
        self.assertEqual(response.data["key"], asset.key)
        self.assertEqual(response.data["version"], 1)

    def test_update_asset_returns_200(self):
        """Test updating an asset returns 200 status code"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        data = {
            "name": "Updated Asset",
            "description": "Updated description",
            "version": asset.version,
        }

        response = self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_asset_returns_updated_data(self):
        """Test updating an asset returns updated response data"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        data = {
            "name": "Updated Asset",
            "description": "Updated description",
            "version": asset.version,
        }

        response = self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")

        self.assertEqual(response.data["name"], "Updated Asset")

    def test_update_asset_updates_database(self):
        """Test updating an asset updates database correctly"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        data = {
            "name": "Updated Asset",
            "description": "Updated description",
            "version": asset.version,
        }

        self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")

        asset.refresh_from_db()
        self.assertEqual(asset.name, "Updated Asset")

    def test_update_asset_increments_version(self):
        """Test updating an asset increments version"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )
        original_version = asset.version

        data = {
            "name": "Updated Asset",
            "description": "Updated description",
            "version": asset.version,
        }

        self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")

        asset.refresh_from_db()
        self.assertEqual(asset.version, original_version + 1)

    def test_update_asset_optimistic_locking(self):
        """Test optimistic locking prevents concurrent updates"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        # Simulate concurrent update: increment version in database
        asset.increment_version()

        # Try to update with old version
        data = {"name": "Updated Asset", "version": 1}  # Old version

        response = self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn(
            response.data.get("code", ""),
            ("ASSET_CONCURRENT_MODIFICATION", "CONCURRENT_MODIFICATION", "CONFLICT"),
            msg="Version conflict should return concurrent modification or conflict code",
        )
        details = response.data.get("details", response.data)
        self.assertEqual(details.get("current_version"), 2)
        self.assertEqual(details.get("expected_version") or details.get("provided_version"), 1)

    def test_delete_asset_returns_204(self):
        """Test deleting an asset returns 204 status code"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        response = self.client.delete(f"/api/v1/assets/{asset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_asset_sets_status_to_retired(self):
        """Test deleting an asset sets status to RETIRED (soft delete)"""
        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        self.client.delete(f"/api/v1/assets/{asset.id}/")

        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.RETIRED)

    def test_list_assets_tenant_scoped(self):
        """Test that users can only see assets in their tenant"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset"
        )

        # Create asset in user's tenant
        my_asset = Asset.objects.create(
            tenant=self.tenant, key="my-asset", name="My Asset", created_by=self.user
        )

        response = self.client.get("/api/v1/assets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]

        # Should only see assets in own tenant
        self.assertIn(str(my_asset.id), asset_ids)
        self.assertNotIn(str(other_asset.id), asset_ids)

    def test_list_assets_filter_by_domain(self):
        """Test filtering assets by domain"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different domains
        marketing_asset = Asset.objects.create(
            tenant=self.tenant,
            key="marketing-asset",
            name="Marketing Asset",
            domain="marketing",
            created_by=self.user,
        )
        finance_asset = Asset.objects.create(
            tenant=self.tenant,
            key="finance-asset",
            name="Finance Asset",
            domain="finance",
            created_by=self.user,
        )

        # Filter by marketing domain
        response = self.client.get("/api/v1/assets/?domain=marketing")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(marketing_asset.id), asset_ids)
        self.assertNotIn(str(finance_asset.id), asset_ids)

    def test_list_assets_filter_by_draft_status(self):
        """Test filtering assets by DRAFT status"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different statuses
        draft_asset = Asset.objects.create(
            tenant=self.tenant,
            key="draft-asset",
            name="Draft Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        active_asset = Asset.objects.create(
            tenant=self.tenant,
            key="active-asset",
            name="Active Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Filter by DRAFT status
        response = self.client.get("/api/v1/assets/?status=DRAFT")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(draft_asset.id), asset_ids)
        self.assertNotIn(str(active_asset.id), asset_ids)

    def test_list_assets_filter_by_active_status(self):
        """Test filtering assets by ACTIVE status"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different statuses
        draft_asset = Asset.objects.create(
            tenant=self.tenant,
            key="draft-asset",
            name="Draft Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        active_asset = Asset.objects.create(
            tenant=self.tenant,
            key="active-asset",
            name="Active Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Filter by ACTIVE status
        response = self.client.get("/api/v1/assets/?status=ACTIVE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(active_asset.id), asset_ids)
        self.assertNotIn(str(draft_asset.id), asset_ids)

    def test_list_assets_filter_by_invalid_status(self):
        """Test filtering assets by invalid status returns empty results"""
        self.client.force_authenticate(user=self.user)

        # Create an asset
        Asset.objects.create(
            tenant=self.tenant, key=self._unique_key("test-asset"), name="Test Asset", created_by=self.user
        )

        # Filter by invalid status
        response = self.client.get("/api/v1/assets/?status=INVALID_STATUS")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_assets_ordering_ascending(self):
        """Test ordering assets by name ascending"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different names
        asset_a = Asset.objects.create(
            tenant=self.tenant, key="asset-a", name="Asset A", created_by=self.user
        )
        asset_b = Asset.objects.create(
            tenant=self.tenant, key="asset-b", name="Asset B", created_by=self.user
        )

        # Order by name ascending
        response = self.client.get("/api/v1/assets/?ordering=name")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in response.data["results"]]
        # Should be ordered by name (A before B)
        asset_a_index = names.index("Asset A")
        asset_b_index = names.index("Asset B")
        self.assertLess(asset_a_index, asset_b_index)

    def test_list_assets_ordering_descending(self):
        """Test ordering assets by name descending"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different names
        asset_a = Asset.objects.create(
            tenant=self.tenant, key="asset-a", name="Asset A", created_by=self.user
        )
        asset_b = Asset.objects.create(
            tenant=self.tenant, key="asset-b", name="Asset B", created_by=self.user
        )

        # Order by name descending
        response = self.client.get("/api/v1/assets/?ordering=-name")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in response.data["results"]]
        asset_a_index = names.index("Asset A")
        asset_b_index = names.index("Asset B")
        # Descending: B should come before A
        self.assertGreater(asset_a_index, asset_b_index)

    def test_list_assets_search(self):
        """Test searching assets returns matching results"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different names
        searchable_asset = Asset.objects.create(
            tenant=self.tenant,
            key="searchable-asset",
            name="Searchable Asset",
            description="This asset can be found",
            created_by=self.user,
        )
        other_asset = Asset.objects.create(
            tenant=self.tenant,
            key="other-asset",
            name="Other Asset",
            description="This asset cannot be found",
            created_by=self.user,
        )

        # Search for "Searchable"
        response = self.client.get("/api/v1/assets/?search=Searchable")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(searchable_asset.id), asset_ids)
        self.assertNotIn(str(other_asset.id), asset_ids)

    def test_list_assets_search_includes_searchable_asset(self):
        """Test searching assets includes searchable asset."""
        self.client.force_authenticate(user=self.user)

        searchable_asset = Asset.objects.create(
            tenant=self.tenant,
            key="searchable-asset",
            name="Searchable Asset",
            description="This asset can be found",
            created_by=self.user,
        )
        Asset.objects.create(
            tenant=self.tenant,
            key="other-asset",
            name="Other Asset",
            description="This asset cannot be found",
            created_by=self.user,
        )

        response = self.client.get("/api/v1/assets/?search=Searchable")
        asset_ids = [a["id"] for a in response.data["results"]]

        self.assertIn(str(searchable_asset.id), asset_ids)

    def test_list_assets_search_excludes_non_searchable_asset(self):
        """Test searching assets excludes non-searchable asset."""
        self.client.force_authenticate(user=self.user)

        Asset.objects.create(
            tenant=self.tenant,
            key="searchable-asset",
            name="Searchable Asset",
            description="This asset can be found",
            created_by=self.user,
        )
        other_asset = Asset.objects.create(
            tenant=self.tenant,
            key="other-asset",
            name="Other Asset",
            description="This asset cannot be found",
            created_by=self.user,
        )

        response = self.client.get("/api/v1/assets/?search=Searchable")
        asset_ids = [a["id"] for a in response.data["results"]]

        self.assertNotIn(str(other_asset.id), asset_ids)

    def test_list_assets_combined_filters(self):
        """Test combining multiple filters"""
        self.client.force_authenticate(user=self.user)

        # Create assets with different combinations
        matching_asset = Asset.objects.create(
            tenant=self.tenant,
            key="matching-asset",
            name="Matching Asset",
            domain="marketing",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        non_matching_asset = Asset.objects.create(
            tenant=self.tenant,
            key="non-matching-asset",
            name="Non Matching Asset",
            domain="finance",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Filter by domain and status
        response = self.client.get("/api/v1/assets/?domain=marketing&status=ACTIVE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(matching_asset.id), asset_ids)
        self.assertNotIn(str(non_matching_asset.id), asset_ids)

    # ========== ERROR HANDLING ==========

    def test_create_asset_unauthenticated(self):
        """Test creating asset without authentication (error handling)"""
        test_key = self._unique_key()
        data = {"key": test_key, "name": "Test Asset"}

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_asset_missing_required_fields(self):
        """Test creating asset with missing required fields (error handling)"""
        self.client.force_authenticate(user=self.user)

        # Missing key
        data = {"name": "Test Asset"}

        response = self.client.post("/api/v1/assets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("key", str(response.data).lower() or response.data)

    def test_create_asset_invalid_status(self):
        """Test creating asset with invalid status value (error handling)"""
        self.client.force_authenticate(user=self.user)

        test_key = self._unique_key()
        data = {"key": test_key, "name": "Test Asset", "status": "INVALID_STATUS"}

        response = self.client.post("/api/v1/assets/", data, format="json")

        # DRF ignores unknown/non-writable fields: "status" is not part of
        # AssetCreateSerializer (it is set automatically to DRAFT), so the
        # extra field is silently discarded and creation succeeds.
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_asset_not_found(self):
        """Test retrieving non-existent asset (error handling)"""
        import uuid

        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/assets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_asset_invalid_uuid(self):
        """Test retrieving asset with invalid UUID format (error handling)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/assets/invalid-uuid/")

        # Should return 404 or 400 depending on URL routing
        self.assertIn(
            response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]
        )

    def test_update_asset_not_found(self):
        """Test updating non-existent asset (error handling)"""
        import uuid

        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        data = {"name": "Updated Asset"}

        response = self.client.patch(f"/api/v1/assets/{fake_id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_asset_tenant_isolation(self):
        """Test updating asset from different tenant (error handling)"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset"
        )

        data = {"name": "Updated Asset"}

        response = self.client.patch(f"/api/v1/assets/{other_asset.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_asset_not_found(self):
        """Test deleting non-existent asset (error handling)"""
        import uuid

        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.delete(f"/api/v1/assets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_asset_tenant_isolation(self):
        """Test deleting asset from different tenant (error handling)"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset"
        )

        response = self.client.delete(f"/api/v1/assets/{other_asset.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_assets_returns_200(self):
        """Test listing assets returns 200"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/assets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_recommendations_no_tenant_returns_empty_list(self):
        """Recommendations endpoint returns 200 with empty list when user has no tenant (graceful degradation)."""
        # User without tenant (e.g. legacy user, platform admin, or pre-migration)
        user_no_tenant = User.objects.create_user(
            email=f"no-tenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)

        response = self.client.get("/api/v1/assets/recommendations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 0)
