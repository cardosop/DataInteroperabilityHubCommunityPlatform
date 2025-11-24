"""
Unit tests for asset serializers.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.assets.serializers import (
    AssetSerializer,
    AssetCreateSerializer,
    AssetUpdateSerializer,
)

User = get_user_model()


class AssetSerializerTest(TestCase):
    """Test asset serializers"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user
        )
    
    def test_asset_serializer(self):
        """Test AssetSerializer serialization"""
        serializer = AssetSerializer(self.asset)
        data = serializer.data
        
        self.assertEqual(data['id'], str(self.asset.id))
        self.assertEqual(data['key'], 'test-asset')
        self.assertEqual(data['name'], 'Test Asset')
        self.assertEqual(data['status'], AssetStatus.DRAFT)
    
    def test_asset_create_serializer(self):
        """Test AssetCreateSerializer validation"""
        serializer = AssetCreateSerializer(data={
            'key': 'new-asset',
            'name': 'New Asset',
            'description': 'New description',
            'visibility': 'INTERNAL'
        })
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['key'], 'new-asset')
        self.assertEqual(serializer.validated_data['name'], 'New Asset')
    
    def test_asset_update_serializer(self):
        """Test AssetUpdateSerializer"""
        serializer = AssetUpdateSerializer(
            instance=self.asset,
            data={
                'name': 'Updated Asset',
                'description': 'Updated description'
            },
            partial=True
        )
        
        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.name, 'Updated Asset')

