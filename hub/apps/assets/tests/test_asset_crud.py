"""
Unit tests for asset CRUD operations.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

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
        
        response = self.client.post("/api/v1/assets/assets/", data, format="json")
        
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
        
        response = self.client.post("/api/v1/assets/assets/", data, format="json")
        
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
        
        response = self.client.get(f"/api/v1/assets/assets/{asset.id}/")
        
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
        
        response = self.client.patch(f"/api/v1/assets/assets/{asset.id}/", data, format="json")
        
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
        
        response = self.client.patch(f"/api/v1/assets/assets/{asset.id}/", data, format="json")
        
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
        
        response = self.client.delete(f"/api/v1/assets/assets/{asset.id}/")
        
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
        
        response = self.client.get("/api/v1/assets/assets/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = [a["id"] for a in response.data["results"]]
        
        # Should only see assets in own tenant
        self.assertIn(str(my_asset.id), asset_ids)
        self.assertNotIn(str(other_asset.id), asset_ids)

