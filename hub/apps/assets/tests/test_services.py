"""
Unit tests for AssetService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase

from hub.apps.assets.services import AssetService
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.services.base import ValidationError, NotFoundError, ConflictError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AssetServiceTest(TestCase):
    """Test AssetService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = AssetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
    
    def test_create_asset_success(self):
        """Test successful asset creation"""
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset",
            description="Test description",
            domain="test-domain"
        )
        
        self.assertIsNotNone(asset)
        self.assertEqual(asset.key, "test-asset")
        self.assertEqual(asset.name, "Test Asset")
        self.assertEqual(asset.status, AssetStatus.DRAFT)
    
    def test_create_asset_duplicate_key(self):
        """Test asset creation with duplicate key"""
        # Create first asset
        self.service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="test-asset",
            name="Test Asset"
        )
        
        # Try to create duplicate
        with self.assertRaises(ConflictError) as cm:
            self.service.create_asset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                key="test-asset",
                name="Another Asset"
            )
        
        self.assertEqual(cm.exception.code, "CONFLICT_ERROR")
    
    def test_update_asset_success(self):
        """Test successful asset update"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Original Name",
            status=AssetStatus.DRAFT
        )
        
        updated = self.service.update_asset(
            asset_id=str(asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            version=asset.version
        )
        
        updated.refresh_from_db()
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.version, asset.version + 1)
    
    def test_update_asset_version_mismatch(self):
        """Test asset update with version mismatch"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Original Name",
            status=AssetStatus.DRAFT
        )
        
        with self.assertRaises(ConflictError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated Name",
                version=999  # Wrong version
            )
        
        self.assertEqual(cm.exception.code, "CONFLICT_ERROR")
    
    def test_update_asset_activation_blocked(self):
        """Test asset activation when requirements not met"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT
        )
        
        # Asset without contract/dataset cannot be activated
        with self.assertRaises(ValidationError) as cm:
            self.service.update_asset(
                asset_id=str(asset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                status=AssetStatus.ACTIVE,
                version=asset.version
            )
        
        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn('ASSET_ACTIVATION_BLOCKED', cm.exception.details.get('code', ''))
    
    def test_delete_asset_success(self):
        """Test successful asset deletion"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )
        
        self.service.delete_asset(
            asset_id=str(asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.RETIRED)
    
    def test_get_asset_success(self):
        """Test successful asset retrieval"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )
        
        retrieved = self.service.get_asset(
            asset_id=str(asset.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(retrieved.id, asset.id)
        self.assertEqual(retrieved.key, asset.key)

