"""
Unit tests for asset CRUD operations.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetCRUDTest(TestCase):
    """Test asset CRUD operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_create_asset(self):
        """Test creating an asset"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "key": "test-asset",
            "name": "Test Asset",
            "description": "Test description",
            "domain": "marketing",
            "visibility": AssetVisibility.INTERNAL
        }
        
        response = self.client.post("/api/v1/assets/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["key"], "test-asset")
        self.assertEqual(response.data["name"], "Test Asset")
        self.assertEqual(response.data["status"], AssetStatus.DRAFT)
        self.assertEqual(response.data["dq_status"], DQStatus.UNKNOWN)
        self.assertEqual(response.data["compliance_status"], ComplianceStatus.UNKNOWN)
        self.assertEqual(response.data["version"], 1)
        
        # Verify asset was created
        asset_id = response.data["id"]
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.tenant, self.tenant)
        self.assertEqual(asset.created_by, self.user)
    
    def test_create_asset_duplicate_key(self):
        """Test creating asset with duplicate key fails"""
        self.client.force_authenticate(user=self.user)
        
        # Create first asset
        Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="First Asset",
            created_by=self.user
        )
        
        # Try to create second asset with same key
        data = {
            "key": "test-asset",
            "name": "Second Asset"
        }
        
        response = self.client.post("/api/v1/assets/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", response.data["error"])
    
    def test_retrieve_asset(self):
        """Test retrieving an asset"""
        self.client.force_authenticate(user=self.user)
        
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        response = self.client.get(f"/api/v1/assets/{asset.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(asset.id))
        self.assertEqual(response.data["key"], "test-asset")
        self.assertEqual(response.data["version"], 1)
    
    def test_update_asset(self):
        """Test updating an asset"""
        self.client.force_authenticate(user=self.user)
        
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        data = {
            "name": "Updated Asset",
            "description": "Updated description",
            "version": asset.version
        }
        
        response = self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Asset")
        
        asset.refresh_from_db()
        self.assertEqual(asset.name, "Updated Asset")
        self.assertEqual(asset.version, 2)  # Version incremented
    
    def test_update_asset_optimistic_locking(self):
        """Test optimistic locking prevents concurrent updates"""
        self.client.force_authenticate(user=self.user)
        
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Simulate concurrent update: increment version in database
        asset.increment_version()
        
        # Try to update with old version
        data = {
            "name": "Updated Asset",
            "version": 1  # Old version
        }
        
        response = self.client.patch(f"/api/v1/assets/{asset.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("CONCURRENT_MODIFICATION", response.data["code"])
        self.assertEqual(response.data["current_version"], 2)
        self.assertEqual(response.data["provided_version"], 1)
    
    def test_delete_asset(self):
        """Test deleting an asset (soft delete)"""
        self.client.force_authenticate(user=self.user)
        
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        response = self.client.delete(f"/api/v1/assets/{asset.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.RETIRED)
    
    def test_list_assets_tenant_scoped(self):
        """Test that users can only see assets in their tenant"""
        self.client.force_authenticate(user=self.user)
        
        # Create another tenant and asset
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset"
        )
        
        # Create asset in user's tenant
        my_asset = Asset.objects.create(
            tenant=self.tenant,
            key="my-asset",
            name="My Asset",
            created_by=self.user
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
            created_by=self.user
        )
        finance_asset = Asset.objects.create(
            tenant=self.tenant,
            key="finance-asset",
            name="Finance Asset",
            domain="finance",
            created_by=self.user
        )
        
        # Filter by marketing domain
        response = self.client.get("/api/v1/assets/?domain=marketing")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(marketing_asset.id), asset_ids)
        self.assertNotIn(str(finance_asset.id), asset_ids)
    
    def test_list_assets_filter_by_status(self):
        """Test filtering assets by status"""
        self.client.force_authenticate(user=self.user)
        
        # Create assets with different statuses
        draft_asset = Asset.objects.create(
            tenant=self.tenant,
            key="draft-asset",
            name="Draft Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user
        )
        active_asset = Asset.objects.create(
            tenant=self.tenant,
            key="active-asset",
            name="Active Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        # Filter by DRAFT status
        response = self.client.get("/api/v1/assets/?status=DRAFT")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(draft_asset.id), asset_ids)
        self.assertNotIn(str(active_asset.id), asset_ids)
        
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
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Filter by invalid status
        response = self.client.get("/api/v1/assets/?status=INVALID_STATUS")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
    
    def test_list_assets_ordering(self):
        """Test ordering assets"""
        self.client.force_authenticate(user=self.user)
        
        # Create assets with different names
        asset_a = Asset.objects.create(
            tenant=self.tenant,
            key="asset-a",
            name="Asset A",
            created_by=self.user
        )
        asset_b = Asset.objects.create(
            tenant=self.tenant,
            key="asset-b",
            name="Asset B",
            created_by=self.user
        )
        
        # Order by name ascending
        response = self.client.get("/api/v1/assets/?ordering=name")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in response.data["results"]]
        # Should be ordered by name (A before B)
        asset_a_index = names.index("Asset A")
        asset_b_index = names.index("Asset B")
        self.assertLess(asset_a_index, asset_b_index)
        
        # Order by name descending
        response = self.client.get("/api/v1/assets/?ordering=-name")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in response.data["results"]]
        # Should be ordered by name descending (B before A)
        asset_a_index = names.index("Asset A")
        asset_b_index = names.index("Asset B")
        self.assertGreater(asset_a_index, asset_b_index)
    
    def test_list_assets_search(self):
        """Test searching assets"""
        self.client.force_authenticate(user=self.user)
        
        # Create assets with different names
        searchable_asset = Asset.objects.create(
            tenant=self.tenant,
            key="searchable-asset",
            name="Searchable Asset",
            description="This asset can be found",
            created_by=self.user
        )
        other_asset = Asset.objects.create(
            tenant=self.tenant,
            key="other-asset",
            name="Other Asset",
            description="This asset cannot be found",
            created_by=self.user
        )
        
        # Search for "Searchable"
        response = self.client.get("/api/v1/assets/?search=Searchable")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(searchable_asset.id), asset_ids)
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
            created_by=self.user
        )
        non_matching_asset = Asset.objects.create(
            tenant=self.tenant,
            key="non-matching-asset",
            name="Non Matching Asset",
            domain="finance",
            status=AssetStatus.DRAFT,
            created_by=self.user
        )
        
        # Filter by domain and status
        response = self.client.get("/api/v1/assets/?domain=marketing&status=ACTIVE")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        self.assertIn(str(matching_asset.id), asset_ids)
        self.assertNotIn(str(non_matching_asset.id), asset_ids)

